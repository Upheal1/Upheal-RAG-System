from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class InteractionType(str, Enum):
    """Allowed interaction types for telemetry."""

    VIEWED = "VIEWED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


class TelemetryRequest(BaseModel):
    """
    Request model for POST /api/telemetry.

    Validates user_id, task_id, and interaction_type.
    """

    user_id: UUID
    task_id: UUID
    interaction_type: InteractionType
    completion_time: Optional[int] = Field(default=None, ge=0)
    drop_off_point: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    xp_earned: int = Field(default=0, ge=0)
    dedupe_key: Optional[UUID] = None

    @field_validator("completion_time")
    @classmethod
    def validate_completion_time(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("completion_time must be >= 0")
        return v


class TelemetryResponse(BaseModel):
    """Response model for telemetry endpoint."""

    log_id: UUID
    user_id: UUID
    task_id: UUID
    interaction_type: InteractionType
    recorded_at: str
    idempotent: bool = False
