"""
Gateway-specific request/response schemas for the roadmap endpoint.

Separates the clean roadmap API contract from legacy clinical fields
used by `AssessGatewayResponse`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from services.shared.schemas import (
    ClinicalTask,
    RoadmapDay,
    ScreenTimeData,
    ScreenTimeInsights,
)


class RoadmapRequest(BaseModel):
    """
    Modern request contract for `POST /api/roadmap`.

    - `user_id` (required): stable identifier for the caller.
    - `screen_time_minutes`: drives sigmoid R_app in personalization.
    - `screenTimeData`: rich per-app screen time from Flutter. When provided,
      `screen_time_minutes` is derived from `totalMinutes`.
    - `answers`: optional GAD-7/PHQ-9 answers dict for form-based scoring.
    - `top_n`: number of tasks to include in the roadmap (1-10).
    """

    user_id: str
    session_id: Optional[str] = None
    locale: str = "en"
    raw_forms_json: Dict[str, Any] = Field(default_factory=dict)
    screen_time_minutes: float = 0.0
    screenTimeData: Optional[ScreenTimeData] = None
    answers: Optional[Dict[str, int]] = None
    top_n: int = Field(default=5, ge=1, le=10)


class RoadmapResponse(BaseModel):
    """
    Clean roadmap response for `POST /api/roadmap`.

    Contains only the roadmap fields — no legacy clinical probabilities,
    severity labels, or RAG recommendations. Designed for new clients.
    """

    user_id: str
    overview_paragraph: str
    suggested_tasks: List[ClinicalTask] = Field(default_factory=list)
    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int
    generated_at: str
    session_id: Optional[str] = None
    version: str = "1.0"
    screen_time_insights: Optional[ScreenTimeInsights] = None
    days: List[RoadmapDay] = Field(default_factory=list)
    total_days: int = 90
    assessment_required: bool = False
