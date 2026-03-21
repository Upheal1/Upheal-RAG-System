from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["assessment"])
def health_check() -> dict:
    return {"status": "ok"}

