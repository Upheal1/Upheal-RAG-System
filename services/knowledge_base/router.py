from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

router = APIRouter()
_kb = None


def _get_kb():
    global _kb
    if _kb is None:
        _kb = ChromaKnowledgeBase()
    return _kb


def _kb_path() -> str:
    from services.shared.pathing import resolve_chroma_path
    return resolve_chroma_path()


class KnowledgeBaseHealthResponse(BaseModel):
    """Phase 1 health spec for the knowledge base service."""

    indexed_tasks: int = Field(..., description="Number of tasks/documents indexed in Chroma")
    storage_status: str = Field(
        ...,
        description="One of: healthy | degraded | unavailable",
    )
    last_ingestion: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp of the last ingestion run, if known",
    )


def _determine_storage_status(healthy: bool, count: int) -> str:
    if not healthy:
        return "unavailable"
    if count == 0:
        return "degraded"
    return "healthy"


def _last_ingestion_from_metadata() -> Optional[str]:
    """Attempt to extract last_ingestion from config.json without loading model."""
    try:
        import json
        from pathlib import Path

        db_path = Path(_kb_path())
        config_path = db_path / "config.json"
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            ts2 = cfg.get("last_ingestion") or cfg.get("built_at")
            if ts2:
                return str(ts2)
    except Exception:
        pass
    return None


@router.get("/health", response_model=KnowledgeBaseHealthResponse, tags=["knowledge_base"])
@router.head("/health", include_in_schema=False)
def health_check() -> KnowledgeBaseHealthResponse:
    """Lightweight health check that doesn't load the embedding model."""
    import os
    from pathlib import Path

    chroma_path = _kb_path()
    healthy = False
    count = 0

    try:
        p = Path(chroma_path)
        if p.is_dir():
            db_file = p / "chroma.sqlite3"
            healthy = db_file.exists()
            if healthy:
                items = [f for f in p.iterdir() if f.is_dir() and len(f.name) == 36 and '-' in f.name]
                count = max(len(items), 1)
    except Exception:
        pass

    status = _determine_storage_status(healthy, count)
    last_ingestion = _last_ingestion_from_metadata()

    return KnowledgeBaseHealthResponse(
        indexed_tasks=count,
        storage_status=status,
        last_ingestion=last_ingestion,
    )
