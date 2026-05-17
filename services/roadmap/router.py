"""
Roadmap service router.

Provides endpoints for roadmap management including status checks.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from services.gateway.auth_middleware import AuthenticatedUser, get_current_user
from services.shared.schemas import ReassessmentStatus
from services.shared.state import SupabaseSyncHook

router = APIRouter(tags=["roadmap"])


@router.get("/{user_id}/status", response_model=ReassessmentStatus)
async def get_roadmap_status(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ReassessmentStatus:
    """
    Check if user needs to retake the assessment.

    Returns assessment_required=True if:
    - No active roadmap exists
    - Current day >= 90
    - Roadmap status is COMPLETED or EXPIRED
    """
    if str(current_user.user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's roadmap status",
        )

    try:
        hook = SupabaseSyncHook("roadmaps")
    except Exception:
        return ReassessmentStatus(
            user_id=user_id,
            assessment_required=True,
            days_since_last_assessment=None,
        )

    result = (
        hook.client.table("roadmaps")
        .select("*")
        .eq("user_id", user_id)
        .order("valid_from", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return ReassessmentStatus(
            user_id=user_id,
            assessment_required=True,
            days_since_last_assessment=None,
        )

    roadmap = result.data[0]
    valid_from_str = roadmap.get("valid_from")
    if not valid_from_str:
        return ReassessmentStatus(
            user_id=user_id,
            roadmap_id=roadmap.get("id"),
            roadmap_status=roadmap.get("status"),
            current_day=1,
            total_days=90,
            assessment_required=True,
            days_since_last_assessment=1,
        )

    try:
        valid_from = datetime.fromisoformat(valid_from_str.replace("Z", "+00:00"))
        days_since = (datetime.now(timezone.utc) - valid_from).days + 1
    except Exception:
        days_since = 1

    current_day = min(days_since, 90)
    roadmap_status = roadmap.get("status", "ACTIVE")
    assessment_required = current_day >= 90 or roadmap_status in [
        "COMPLETED",
        "EXPIRED",
    ]

    return ReassessmentStatus(
        user_id=user_id,
        roadmap_id=roadmap.get("id"),
        roadmap_status=roadmap_status,
        current_day=current_day,
        total_days=90,
        assessment_required=assessment_required,
        days_since_last_assessment=days_since,
    )


@router.get("/health")
@router.head("/health", include_in_schema=False)
async def health():
    """Health check for roadmap service."""
    return {"status": "ok"}
