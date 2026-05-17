from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["assessment"])
@router.head("/health", include_in_schema=False)
def health_check() -> dict:
    return {"status": "ok"}

