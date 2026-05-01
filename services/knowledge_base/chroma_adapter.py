from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from services.shared.logging import get_logger
from services.shared.pathing import repo_root
from services.shared.schemas import ClinicalTask, UserContext


logger = get_logger(__name__)


def _difficulty_from_metadata(meta: Dict[str, Any]) -> int:
    raw = meta.get("difficulty")
    if raw is not None:
        try:
            d = int(raw)
            return max(1, min(5, d))
        except (TypeError, ValueError):
            pass
    header = meta.get("header")
    header_str = str(header).lower() if header is not None else ""
    if "high" in header_str:
        return 4
    if "low" in header_str:
        return 2
    if "moderate" in header_str:
        return 3
    return 3


def _xp_from_metadata(meta: Dict[str, Any]) -> int:
    raw = meta.get("xp_reward")
    if raw is None:
        return 10
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 10


def _symptom_tags_from_metadata(
    meta: Dict[str, Any], fallback: List[str]
) -> List[str]:
    raw = meta.get("clinical_tags")
    if isinstance(raw, str) and raw.strip():
        return [t.strip() for t in raw.split(",") if t.strip()]
    return list(fallback)


def _build_where_filter(user_context: UserContext) -> Optional[Dict[str, Any]]:
    """
    Metadata from enriched index uses `tag_primary` (anxiety | depression | general).
    Omit filter if we cannot derive tags or only suicidal/general.
    """
    tags: List[str] = []
    for k, v in user_context.form_scores.items():
        if k in ("general", "suicidal"):
            continue
        if int(v) > 0 and k in ("anxiety", "depression"):
            tags.append(k)
    if not tags:
        return None
    or_clauses = [{"tag_primary": t} for t in tags]
    or_clauses.append({"tag_primary": "general"})
    if len(or_clauses) == 1:
        return or_clauses[0]
    return {"$or": or_clauses}


class ChromaKnowledgeBase:
    """
    Chroma adapter: semantic search plus optional metadata filter when using
    an enriched index (see `services/ingestion/build_index.py`).
    """

    def __init__(
        self,
        *,
        vector_db_path: Optional[str] = None,
        collection_name: Optional[str] = None,
        model_name: str = "all-mpnet-base-v2",
    ):
        root = repo_root()
        self.vector_db_path = vector_db_path or os.environ.get(
            "UPHEAL_CHROMA_PATH", str(root / "data" / "vector_db_mini")
        )
        self.collection_name = collection_name or os.environ.get(
            "UPHEAL_CHROMA_COLLECTION", "clinical_rag_mini"
        )
        self.model_name = model_name

        self._model = None
        self._client = None
        self._collection = None

    def _ensure_loaded(self) -> None:
        if self._collection is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import chromadb
        except Exception as e:
            logger.warning("Knowledge base deps not available: %s", e)
            return

        logger.info("Loading vector DB: %s", self.vector_db_path)
        self._model = SentenceTransformer(self.model_name)

        vector_db_path = self.vector_db_path
        if vector_db_path.startswith("http://") or vector_db_path.startswith("https://"):
            logger.info("Using HTTP ChromaDB client: %s", vector_db_path)
            self._client = chromadb.HttpClient(host=vector_db_path)
        else:
            self._client = chromadb.PersistentClient(path=vector_db_path)
        self._collection = self._client.get_collection(name=self.collection_name)

    def is_healthy(self) -> bool:
        self._ensure_loaded()
        if self._collection is None:
            return False
        try:
            return self._collection.count() > 0
        except Exception:
            return False

    def get_document_count(self) -> int:
        self._ensure_loaded()
        if self._collection is None:
            return 0
        try:
            return int(self._collection.count())
        except Exception:
            return 0

    def retrieve_tasks(
        self,
        user_context: UserContext,
        *,
        query_text: Optional[str] = None,
        top_k: int = 5,
    ) -> List[ClinicalTask]:
        self._ensure_loaded()
        if self._collection is None or self._model is None:
            return []

        clinical_tags: List[str] = [
            k for k in user_context.form_scores.keys() if isinstance(k, str)
        ]
        if not clinical_tags:
            clinical_tags = ["general"]

        query_text = query_text or " ".join(clinical_tags)

        query_embedding = self._model.encode([query_text])
        where = _build_where_filter(user_context)
        n_fetch = min(max(top_k * 4, 15), 50)  # Tuned n_fetch slightly higher for better reranking

        where_document = None
        if query_text:
            # Build basic where_document containing top keyword
            search_terms = [t for t in query_text.split() if len(t) > 3]
            if search_terms:
                where_document = {"$contains": search_terms[0].lower()}

        try:
            kwargs = {
                "query_embeddings": query_embedding.tolist(),
                "n_results": n_fetch,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where
            if where_document:
                kwargs["where_document"] = where_document
                
            results = self._collection.query(**kwargs)
        except Exception as e:
            logger.debug("Chroma query with where failed (%s), retrying without filter", e)
            results = self._collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=n_fetch,
                include=["documents", "metadatas", "distances"],
            )

        tasks: List[ClinicalTask] = []
        ids_list = results.get("ids") or [[]]
        doc_row = results["documents"][0]
        meta_row = results["metadatas"][0]
        dist_row = results["distances"][0]
        id_row = ids_list[0] if ids_list else []

        for i, (doc, meta, dist) in enumerate(zip(doc_row, meta_row, dist_row)):
            distance = float(dist) if dist is not None else 1.0
            similarity01 = 1.0 - distance
            similarity01 = max(0.0, min(1.0, similarity01))

            meta_dict = meta if isinstance(meta, dict) else {}
            header = meta_dict.get("header")
            source_reference = str(meta_dict.get("source_file", "Unknown"))
            pages = meta_dict.get("page_numbers")
            symptom_tags = _symptom_tags_from_metadata(meta_dict, clinical_tags)
            difficulty = _difficulty_from_metadata(meta_dict)
            xp_reward = _xp_from_metadata(meta_dict)

            chunk_id = id_row[i] if i < len(id_row) else f"kb_task_{i}"

            tasks.append(
                ClinicalTask(
                    task_id=str(chunk_id),
                    content=str(doc),
                    symptom_tags=symptom_tags,
                    difficulty=difficulty,
                    xp_reward=xp_reward,
                    source_reference=source_reference,
                    metadata={
                        "similarity": float(similarity01),
                        "distance": float(distance),
                        "pages": str(pages) if pages is not None else None,
                        "section": str(header) if header is not None else None,
                        "tag_primary": meta_dict.get("tag_primary"),
                    },
                )
            )

        return tasks[:top_k]
