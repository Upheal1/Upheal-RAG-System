from __future__ import annotations

from fastapi import APIRouter

from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

router = APIRouter()

_kb = ChromaKnowledgeBase()


@router.get("/health", tags=["knowledge_base"])
def health_check() -> dict:
    return {
        "status": "ok",
        "vector_db_healthy": _kb.is_healthy(),
        "total_documents": _kb.get_document_count(),
    }

