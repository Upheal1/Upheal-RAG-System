from __future__ import annotations

from typing import List, Optional, Sequence

from services.shared.logging import get_logger
from services.shared.pathing import repo_root
from services.shared.schemas import ClinicalTask, UserContext


logger = get_logger(__name__)


class ChromaKnowledgeBase:
    """
    Minimal Chroma adapter.

    The current repo already has a working Chroma client in `src/api/rag_client.py`.
    This class is designed to evolve toward the plan's "hybrid search + filtering"
    interface while staying import-safe for scaffolding.
    """

    def __init__(
        self,
        *,
        vector_db_path: Optional[str] = None,
        collection_name: str = "clinical_rag_mini",
        model_name: str = "all-mpnet-base-v2",
    ):
        self.vector_db_path = vector_db_path or str(repo_root() / "data" / "vector_db_mini")
        self.collection_name = collection_name
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
        self._client = chromadb.PersistentClient(path=self.vector_db_path)
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
        """
        Retrieve candidate tasks from Chroma and map them into `ClinicalTask`.

        - Similarity is normalized to [0..1] and stored in `task.metadata["similarity"]`.
        - `task.symptom_tags` is derived from `user_context.form_scores` keys.
        """
        self._ensure_loaded()
        if self._collection is None or self._model is None:
            return []

        clinical_tags: List[str] = [k for k in user_context.form_scores.keys() if isinstance(k, str)]
        if not clinical_tags:
            clinical_tags = ["general"]

        query_text = query_text or " ".join(clinical_tags)

        query_embedding = self._model.encode([query_text])
        results = self._collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        tasks: List[ClinicalTask] = []
        for i, (doc, meta, dist) in enumerate(
            zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
        ):
            distance = float(dist) if dist is not None else 1.0
            similarity01 = 1.0 - distance
            if similarity01 < 0.0:
                similarity01 = 0.0
            if similarity01 > 1.0:
                similarity01 = 1.0

            header = meta.get("header") if isinstance(meta, dict) else None
            header_str = str(header).lower() if header is not None else ""
            if "high" in header_str:
                difficulty = 4
            elif "low" in header_str:
                difficulty = 2
            elif "moderate" in header_str:
                difficulty = 3
            else:
                difficulty = 3

            source_reference = str(meta.get("source_file", "Unknown")) if isinstance(meta, dict) else "Unknown"
            pages = meta.get("page_numbers") if isinstance(meta, dict) else None

            tasks.append(
                ClinicalTask(
                    task_id=f"kb_task_{i}",
                    content=str(doc),
                    symptom_tags=clinical_tags,
                    difficulty=difficulty,
                    xp_reward=10,
                    source_reference=source_reference,
                    metadata={
                        "similarity": float(similarity01),
                        "distance": float(distance),
                        "pages": str(pages) if pages is not None else None,
                        "section": str(header) if header is not None else None,
                    },
                )
            )

        return tasks

