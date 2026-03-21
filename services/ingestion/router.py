from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["ingestion"])
def health_check() -> dict:
    return {"status": "ok"}

