"""
Pydantic models for the Clinical Auditor microservice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HotlineResource(BaseModel):
    """A single emergency hotline entry."""

    name: str
    number: str
    description: str


class EmergencyPayload(BaseModel):
    """Structured emergency response returned on RED safety audits."""

    message: str
    hotlines: List[HotlineResource]
    immediate_action: str = Field(
        default="Contact emergency services or a crisis helpline immediately."
    )
    locale: str = "en"


class AuditFlags(BaseModel):
    """Individual flags raised during the audit."""

    crisis_detected: bool = False
    crisis_keywords_found: List[str] = Field(default_factory=list)
    robotic_tone_detected: bool = False
    safety_risk_task_found: bool = False
    safety_risk_task_ids: List[str] = Field(default_factory=list)
    frustration_detected: bool = False
    frustration_score: float = 0.0


class AuditResult(BaseModel):
    """Complete audit output for a roadmap."""

    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int
    emergency_payload: Optional[EmergencyPayload] = None
    flags: AuditFlags = Field(default_factory=AuditFlags)
    overview_paragraph: str
    task_ids: List[str] = Field(default_factory=list)
    frustration_score: float = 0.0
    amber_advisory: bool = False


class AuditRequest(BaseModel):
    """Request body for POST /audit endpoint."""

    user_id: str
    overview_paragraph: str
    task_contents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of ClinicalTask-like dicts with at least task_id, content, symptom_tags, safety_risk.",
    )
    locale: str = "en"
