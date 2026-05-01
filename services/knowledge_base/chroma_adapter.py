from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from services.shared.logging import get_logger
from services.shared.pathing import repo_root
from services.shared.schemas import ClinicalTask, RetrievalQuery, UserContext


logger = get_logger(__name__)


DIGITAL_DETOX_TAGS = {"digital-detox", "screen-time", "phone-addiction", "social-media"}


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


def _symptom_tags_from_metadata(meta: Dict[str, Any], fallback: List[str]) -> List[str]:
    raw = meta.get("clinical_tags")
    if isinstance(raw, str) and raw.strip():
        return [t.strip() for t in raw.split(",") if t.strip()]
    return list(fallback)


def _safety_risk_from_metadata(meta: Dict[str, Any]) -> bool:
    raw = meta.get("safety_risk")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.lower() in ("true", "1", "yes")
    return False


def _utility_score_from_metadata(meta: Dict[str, Any]) -> float:
    raw = meta.get("utility_score")
    if raw is None:
        return 0.5
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.5


def _build_where_filter(
    user_context: UserContext,
    query: RetrievalQuery,
) -> Optional[Dict[str, Any]]:
    """
    Build ChromaDB metadata filter from UserContext form_scores (tag_primary mapping)
    and RetrievalQuery.max_difficulty ceiling.

    Separation of concerns:
    - Tag filter: OR clause over allowed tag_primary values.
    - Difficulty filter: standalone $lte constraint.
    - Combined: $and of both only when both are semantically required.

    Returns None when no meaningful retrieval signal exists.
    Difficulty is never a standalone filter.
    """
    tag_clauses: List[Dict[str, Any]] = []

    for k, v in user_context.form_scores.items():
        if k in ("general", "suicidal"):
            continue
        if int(v) > 0 and k in ("anxiety", "depression"):
            tag_clauses.append({"tag_primary": k})

    if not tag_clauses:
        return None

    tag_clauses.append({"tag_primary": "general"})
    tag_filter = tag_clauses[0] if len(tag_clauses) == 1 else {"$or": tag_clauses}

    effective_max = query.max_difficulty if query.max_difficulty is not None else 5
    if effective_max >= 5:
        return tag_filter

    difficulty_clause: Dict[str, Any] = {"difficulty": {"$lte": effective_max}}
    return {"$and": [tag_filter, difficulty_clause]}


def _build_where_document_filter(query_text: str) -> Optional[Dict[str, Any]]:
    if not query_text:
        return None
    search_terms = [t for t in query_text.split() if len(t) > 3]
    if not search_terms:
        return None
    return {"$contains": search_terms[0].lower()}


class ChromaKnowledgeBase:
    """
    Chroma adapter: semantic search plus optional metadata filter when using
    an enriched index (see `services/ingestion/build_index.py`).

    Uses HNSW with cosine similarity for ANN retrieval.  The collection is
    created / opened with explicit metadata so that `hnsw:space` is always
    ``cosine`` regardless of the client version.
    """

    def __init__(
        self,
        *,
        vector_db_path: Optional[str] = None,
        collection_name: Optional[str] = None,
        model_name: str = "all-mpnet-base-v2",
        hnsw_ef_search: int = 128,
        hnsw_ef_construction: int = 200,
        hnsw_m: int = 16,
    ):
        root = repo_root()
        self.vector_db_path = vector_db_path or os.environ.get(
            "UPHEAL_CHROMA_PATH", str(root / "data" / "vector_db_mini")
        )
        self.collection_name = collection_name or os.environ.get(
            "UPHEAL_CHROMA_COLLECTION", "clinical_rag_mini"
        )
        self.model_name = model_name
        self.hnsw_ef_search = hnsw_ef_search
        self.hnsw_ef_construction = hnsw_ef_construction
        self.hnsw_m = hnsw_m

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

        vector_db_path = str(self.vector_db_path)
        if vector_db_path.startswith("http://") or vector_db_path.startswith(
            "https://"
        ):
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

    def get_collection_metadata(self) -> Dict[str, Any]:
        """Return the collection-level metadata dict (may include last_ingestion)."""
        self._ensure_loaded()
        if self._collection is None:
            return {}
        try:
            # ChromaDB collections expose metadata via the attribute or get_model.
            meta = getattr(self._collection, "metadata", None)
            if isinstance(meta, dict):
                return dict(meta)
            return {}
        except Exception:
            return {}

    def retrieve_tasks(
        self,
        query: RetrievalQuery,
        user_context: UserContext,
        *,
        top_k: int = 5,
    ) -> List[ClinicalTask]:
        self._ensure_loaded()
        if self._collection is None or self._model is None:
            return []

        query_text = query.query_text or " ".join(query.symptom_keywords)
        if not query_text:
            query_text = (
                " ".join(
                    k
                    for k in user_context.form_scores.keys()
                    if k not in ("general", "suicidal")
                )
                or "general wellness"
            )

        query_embedding = self._model.encode([query_text])
        where = _build_where_filter(user_context, query)
        n_fetch = min(max(top_k * 4, 15), 50)
        where_document = _build_where_document_filter(query_text)

        try:
            kwargs: Dict[str, Any] = {
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
            logger.debug(
                "Chroma query with where failed (%s), retrying without filter", e
            )
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
            symptom_tags = _symptom_tags_from_metadata(
                meta_dict, query.symptom_keywords
            )
            difficulty = _difficulty_from_metadata(meta_dict)
            xp_reward = _xp_from_metadata(meta_dict)
            safety_risk = _safety_risk_from_metadata(meta_dict)
            utility_score = _utility_score_from_metadata(meta_dict)

            chunk_id = id_row[i] if i < len(id_row) else f"kb_task_{i}"

            tasks.append(
                ClinicalTask(
                    task_id=str(chunk_id),
                    content=str(doc),
                    symptom_tags=symptom_tags,
                    difficulty=difficulty,
                    xp_reward=xp_reward,
                    safety_risk=safety_risk,
                    utility_score=utility_score,
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

        if query.boost_digital_detox:
            tasks = self._apply_digital_detox_boost(tasks)

        return tasks[:top_k]

    def _apply_digital_detox_boost(
        self, tasks: List[ClinicalTask]
    ) -> List[ClinicalTask]:
        detox_tasks: List[ClinicalTask] = []
        non_detox_tasks: List[ClinicalTask] = []

        for task in tasks:
            task_tags_lower = {t.lower() for t in task.symptom_tags}
            if task_tags_lower & DIGITAL_DETOX_TAGS:
                detox_tasks.append(task)
            else:
                non_detox_tasks.append(task)

        return detox_tasks + non_detox_tasks
