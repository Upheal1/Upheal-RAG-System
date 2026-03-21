from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class ClinicalTask(BaseModel):
    """
    A single actionable clinical-style recommendation candidate.
    """

    task_id: str
    content: str
    symptom_tags: List[str]
    difficulty: int = Field(..., ge=1, le=5)
    xp_reward: int
    source_reference: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserContext(BaseModel):
    user_id: str
    timestamp: str
    form_scores: Dict[str, int] = Field(default_factory=dict)
    app_exposure_ratios: Dict[str, float] = Field(default_factory=dict)
    user_stats: Dict[str, int] = Field(default_factory=dict)


class FinalRoadmap(BaseModel):
    user_id: str
    overview_paragraph: str
    suggested_tasks: List[ClinicalTask] = Field(default_factory=list)
    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int

