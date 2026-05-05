"""
ClinicalAuditor — safety gate for all client-facing roadmap responses.

Detects crisis keywords (EN/AR), robotic tone, and tasks flagged with
safety_risk=True. Returns structured EmergencyPayload with hotline data
when a RED audit is triggered.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from services.auditor.i18n import (
    CRISIS_KEYWORDS_AR,
    CRISIS_KEYWORDS_EN,
    GUIDANCE_MESSAGES,
    HOTLINES,
    ROBOTIC_TONE_KEYWORDS,
    resolve_locale,
)
from services.auditor.schemas import (
    AuditFlags,
    AuditResult,
    EmergencyPayload,
    HotlineResource,
)
from services.auditor.sentiment import SentimentClassifier
from services.shared.schemas import ClinicalTask, FinalRoadmap


class ClinicalAuditor:
    """Stateless auditor that inspects text and tasks for safety flags."""

    def __init__(self, locale: str = "en") -> None:
        self._locale = resolve_locale(locale)
        self._sentiment = SentimentClassifier(locale=self._locale)

    # ------------------------------------------------------------------
    # Crisis detection
    # ------------------------------------------------------------------

    def _get_crisis_keywords(self) -> List[str]:
        if self._locale == "ar":
            return CRISIS_KEYWORDS_AR + CRISIS_KEYWORDS_EN
        return CRISIS_KEYWORDS_EN

    def detect_crisis(self, text: str) -> tuple[bool, List[str]]:
        """Return (is_crisis, list_of_matched_keywords)."""
        lower = text.lower()
        matched = [kw for kw in self._get_crisis_keywords() if kw.lower() in lower]
        return bool(matched), matched

    # ------------------------------------------------------------------
    # Robotic tone detection
    # ------------------------------------------------------------------

    def detect_robotic_tone(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in ROBOTIC_TONE_KEYWORDS)

    # ------------------------------------------------------------------
    # Safety-risk task scan  (works around missing Gamifier)
    # ------------------------------------------------------------------

    @staticmethod
    def scan_safety_risk_tasks(
        tasks: Sequence[ClinicalTask],
    ) -> tuple[bool, List[str]]:
        """Return (has_risky_task, list_of_risky_task_ids)."""
        risky_ids = [t.task_id for t in tasks if t.safety_risk]
        return bool(risky_ids), risky_ids

    # ------------------------------------------------------------------
    # Build emergency payload
    # ------------------------------------------------------------------

    def _build_emergency_payload(self) -> EmergencyPayload:
        hotline_list = HOTLINES.get(self._locale, HOTLINES["en"])
        return EmergencyPayload(
            message=GUIDANCE_MESSAGES[self._locale]["red"],
            hotlines=[HotlineResource(**h) for h in hotline_list],
            immediate_action=(
                "Contact emergency services or a crisis helpline immediately."
                if self._locale == "en"
                else "تواصل مع خدمات الطوارئ أو خط مساعدة الأزمات فورًا."
            ),
            locale=self._locale,
        )

    # ------------------------------------------------------------------
    # Primary audit entry point — works on FinalRoadmap + raw tasks
    # ------------------------------------------------------------------

    def _compute_frustration(
        self,
        roadmap: FinalRoadmap,
    ) -> tuple[bool, float, bool]:
        """Compute frustration score from overview paragraph.

        Returns:
            tuple: (frustration_detected, frustration_score, amber_advisory)
        """
        text = roadmap.overview_paragraph or ""
        score = self._sentiment.classify(text)
        frustration_detected = score > 0.0
        amber_advisory = self._sentiment.is_amber_advisory(score)
        return frustration_detected, score, amber_advisory

    def audit(
        self,
        roadmap: FinalRoadmap,
        tasks: Sequence[ClinicalTask] | None = None,
    ) -> AuditResult:
        """
        Run all safety checks and return an AuditResult.

        Priority order:
        1. Any task with safety_risk=True → RED (hard override)
        2. Crisis keywords in text → RED
        3. Robotic tone → YELLOW
        4. Otherwise → GREEN

        Frustration detection runs on all paths but does NOT override
        RED/YELLOW status - it's added as additional metadata.
        """
        text = (roadmap.overview_paragraph or "").lower()

        # --- compute frustration (runs on all paths) ---
        frustration_detected, frustration_score, amber_advisory = (
            self._compute_frustration(roadmap)
        )

        # --- scan tasks for safety_risk flag ---
        if tasks is not None:
            has_risky, risky_ids = self.scan_safety_risk_tasks(tasks)
        else:
            has_risky, risky_ids = False, []

        # If any task is marked safety_risk=True, force RED regardless of text.
        if has_risky:
            crisis_found, matched_kw = self.detect_crisis(text)
            return AuditResult(
                safety_status="RED",
                next_checkup_days=1,
                emergency_payload=self._build_emergency_payload(),
                flags=AuditFlags(
                    crisis_detected=crisis_found,
                    crisis_keywords_found=matched_kw,
                    safety_risk_task_found=True,
                    safety_risk_task_ids=risky_ids,
                    frustration_detected=frustration_detected,
                    frustration_score=frustration_score,
                ),
                overview_paragraph=GUIDANCE_MESSAGES[self._locale]["red"],
                task_ids=[t.task_id for t in tasks] if tasks else [],
                frustration_score=frustration_score,
                amber_advisory=amber_advisory,
            )

        # --- crisis keyword detection ---
        crisis_found, matched_kw = self.detect_crisis(text)
        if crisis_found:
            return AuditResult(
                safety_status="RED",
                next_checkup_days=1,
                emergency_payload=self._build_emergency_payload(),
                flags=AuditFlags(
                    crisis_detected=True,
                    crisis_keywords_found=matched_kw,
                    frustration_detected=frustration_detected,
                    frustration_score=frustration_score,
                ),
                overview_paragraph=GUIDANCE_MESSAGES[self._locale]["red"],
                task_ids=[t.task_id for t in roadmap.suggested_tasks],
                frustration_score=frustration_score,
                amber_advisory=amber_advisory,
            )

        # --- robotic tone ---
        if self.detect_robotic_tone(text):
            return AuditResult(
                safety_status="YELLOW",
                next_checkup_days=7,
                flags=AuditFlags(
                    robotic_tone_detected=True,
                    frustration_detected=frustration_detected,
                    frustration_score=frustration_score,
                ),
                overview_paragraph=GUIDANCE_MESSAGES[self._locale]["yellow"],
                task_ids=[t.task_id for t in roadmap.suggested_tasks],
                frustration_score=frustration_score,
                amber_advisory=amber_advisory,
            )

        # --- safe ---
        return AuditResult(
            safety_status="GREEN",
            next_checkup_days=14,
            flags=AuditFlags(
                frustration_detected=frustration_detected,
                frustration_score=frustration_score,
            ),
            overview_paragraph=roadmap.overview_paragraph,
            task_ids=[t.task_id for t in roadmap.suggested_tasks],
            frustration_score=frustration_score,
            amber_advisory=amber_advisory,
        )

    # ------------------------------------------------------------------
    # In-place mutator for backward compatibility with audit_roadmap()
    # ------------------------------------------------------------------

    def apply_to_roadmap(
        self,
        roadmap: FinalRoadmap,
        tasks: Sequence[ClinicalTask] | None = None,
    ) -> FinalRoadmap:
        """Mutate the roadmap in-place and return it (legacy compat)."""
        result = self.audit(roadmap, tasks=tasks)
        roadmap.safety_status = result.safety_status
        roadmap.next_checkup_days = result.next_checkup_days
        roadmap.overview_paragraph = result.overview_paragraph

        if result.safety_status == "RED":
            emergency_content = (
                result.emergency_payload.message
                if result.emergency_payload
                else GUIDANCE_MESSAGES[self._locale]["red"]
            )
            roadmap.suggested_tasks = [
                ClinicalTask(
                    task_id="emergency_resources",
                    content=emergency_content,
                    symptom_tags=["suicidal"],
                    difficulty=5,
                    xp_reward=0,
                    safety_risk=False,
                    utility_score=0.0,
                    source_reference="auditor",
                    metadata={},
                )
            ]

        return roadmap


# -----------------------------------------------------------------------
# Module-level convenience function (backward-compatible drop-in for
# services.architect.auditor.audit_roadmap)
# -----------------------------------------------------------------------


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
    - If crisis keywords detected → RED with emergency payload
    - If robotic tone detected → YELLOW
    - Otherwise → GREEN
    """
    auditor = ClinicalAuditor(locale=locale)
    return auditor.apply_to_roadmap(roadmap, tasks=tasks)
