"""
Backward-compatible wrapper: re-exports the Clinical Auditor microservice.

All logic now lives in `services.auditor.core`. This module exists so
existing imports (`from services.architect.auditor import audit_roadmap`)
continue to work without changes.
"""

from __future__ import annotations

from typing import Sequence

from services.auditor.core import ClinicalAuditor
from services.shared.schemas import ClinicalTask, FinalRoadmap

# Re-export the new keywords for any downstream consumers that imported them
# from the old module location.
from services.auditor.i18n import (
    CRISIS_KEYWORDS_EN,
    CRISIS_KEYWORDS_AR,
    GUIDANCE_MESSAGES,
    HOTLINES,
    ROBOTIC_TONE_KEYWORDS,
)

__all__ = [
    "audit_roadmap",
    "ClinicalAuditor",
    "CRISIS_KEYWORDS_EN",
    "CRISIS_KEYWORDS_AR",
    "GUIDANCE_MESSAGES",
    "HOTLINES",
    "ROBOTIC_TONE_KEYWORDS",
]


def audit_roadmap(
    roadmap: FinalRoadmap,
    *,
    locale: str = "en",
    tasks: Sequence[ClinicalTask] | None = None,
) -> FinalRoadmap:
    """
    Audit the roadmap text and task list for safety concerns.

    Safety rules:
    - If any task has safety_risk=True → RED override
    - If crisis keywords detected → RED with emergency resources
    - If robotic tone detected → YELLOW
    - Otherwise → GREEN
    """
    auditor = ClinicalAuditor(locale=locale)
    return auditor.apply_to_roadmap(roadmap, tasks=tasks)
