"""
Comprehensive unit tests for the Clinical Auditor microservice.

Covers:
- GREEN / YELLOW / RED paths
- English and Arabic crisis keywords
- safety_risk=True task override
- Structured emergency payload (hotlines)
- Robotic tone detection
- Backward compatibility with legacy audit_roadmap()
- Edge cases (empty text, missing fields, mixed locale)
"""

from __future__ import annotations

from typing import List

import pytest

from services.auditor.core import ClinicalAuditor, audit_roadmap
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
    AuditRequest,
    AuditResult,
    EmergencyPayload,
    HotlineResource,
)
from services.shared.schemas import ClinicalTask, FinalRoadmap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_roadmap(
    overview: str = "Here are next steps for wellness.",
    tasks: List[ClinicalTask] | None = None,
) -> FinalRoadmap:
    return FinalRoadmap(
        user_id="test-user",
        overview_paragraph=overview,
        suggested_tasks=tasks or [],
        safety_status="GREEN",
        next_checkup_days=14,
    )


def _make_task(**overrides) -> ClinicalTask:
    defaults = dict(
        task_id="t-1",
        content="Breathe deeply for 2 minutes.",
        symptom_tags=["anxiety"],
        difficulty=1,
        xp_reward=50,
        safety_risk=False,
        utility_score=0.7,
        source_reference="test",
        metadata={},
    )
    defaults.update(overrides)
    return ClinicalTask(**defaults)


# ===================================================================
# 1. resolve_locale
# ===================================================================


class TestResolveLocale:
    def test_en_default(self):
        assert resolve_locale("en") == "en"

    def test_ar_detected(self):
        assert resolve_locale("ar") == "ar"

    def test_ar_egypt(self):
        assert resolve_locale("ar-EG") == "ar"

    def test_unknown_falls_back_to_en(self):
        assert resolve_locale("fr") == "en"
        assert resolve_locale("") == "en"


# ===================================================================
# 2. i18n constants sanity
# ===================================================================


class TestI18nConstants:
    def test_en_crisis_keywords_nonempty(self):
        assert len(CRISIS_KEYWORDS_EN) >= 10

    def test_ar_crisis_keywords_nonempty(self):
        assert len(CRISIS_KEYWORDS_AR) >= 10

    def test_no_arabic_in_en_list(self):
        for kw in CRISIS_KEYWORDS_EN:
            assert not any("\u0600" <= c <= "\u06ff" for c in kw)

    def test_no_english_in_ar_list(self):
        for kw in CRISIS_KEYWORDS_AR:
            assert not any("a" <= c.lower() <= "z" for c in kw)

    def test_robotic_keywords_nonempty(self):
        assert len(ROBOTIC_TONE_KEYWORDS) >= 5

    def test_guidance_messages_complete(self):
        for loc in ("en", "ar"):
            assert "red" in GUIDANCE_MESSAGES[loc]
            assert "yellow" in GUIDANCE_MESSAGES[loc]

    def test_hotlines_exist_for_both_locales(self):
        for loc in ("en", "ar"):
            assert loc in HOTLINES
            assert len(HOTLINES[loc]) >= 2

    def test_hotline_shape(self):
        for loc, entries in HOTLINES.items():
            for entry in entries:
                assert "name" in entry
                assert "number" in entry
                assert "description" in entry


# ===================================================================
# 3. Crisis detection
# ===================================================================


class TestCrisisDetection:
    def test_no_crisis(self):
        a = ClinicalAuditor(locale="en")
        found, matched = a.detect_crisis("feeling a bit anxious today")
        assert found is False
        assert matched == []

    def test_single_english_keyword(self):
        a = ClinicalAuditor(locale="en")
        found, matched = a.detect_crisis("I want to die")
        assert found is True
        assert "want to die" in matched

    def test_case_insensitive(self):
        a = ClinicalAuditor(locale="en")
        found, matched = a.detect_crisis("I WANT TO DIE NOW")
        assert found is True

    def test_multiple_keywords(self):
        a = ClinicalAuditor(locale="en")
        found, matched = a.detect_crisis("I feel suicidal and want to end my life")
        assert found is True
        assert len(matched) >= 2

    def test_arabic_crisis_keyword(self):
        a = ClinicalAuditor(locale="ar")
        found, matched = a.detect_crisis("أريد الموت")
        assert found is True

    def test_arabic_auditor_detects_english_too(self):
        """Arabic-mode auditor should also catch English keywords."""
        a = ClinicalAuditor(locale="ar")
        found, _ = a.detect_crisis("I feel suicidal")
        assert found is True

    def test_substring_not_false_positive(self):
        """Keywords like 'suicide' should not match 'resilience'."""
        a = ClinicalAuditor(locale="en")
        found, _ = a.detect_crisis("building resilience is important")
        assert found is False


# ===================================================================
# 4. Robotic tone detection
# ===================================================================


class TestRoboticToneDetection:
    def test_robotic_detected(self):
        a = ClinicalAuditor(locale="en")
        assert a.detect_robotic_tone("As an AI language model I can help") is True

    def test_robotic_medical_disclaimer(self):
        a = ClinicalAuditor(locale="en")
        assert a.detect_robotic_tone("I am not a doctor") is True

    def test_normal_text_not_robotic(self):
        a = ClinicalAuditor(locale="en")
        assert a.detect_robotic_tone("Here are some steps to try.") is False


# ===================================================================
# 5. Safety-risk task scanning
# ===================================================================


class TestSafetyRiskTaskScan:
    def test_no_risky_tasks(self):
        tasks = [_make_task(task_id="t1"), _make_task(task_id="t2")]
        has_risky, ids = ClinicalAuditor.scan_safety_risk_tasks(tasks)
        assert has_risky is False
        assert ids == []

    def test_one_risky_task(self):
        tasks = [
            _make_task(task_id="t1", safety_risk=True),
            _make_task(task_id="t2"),
        ]
        has_risky, ids = ClinicalAuditor.scan_safety_risk_tasks(tasks)
        assert has_risky is True
        assert ids == ["t1"]

    def test_all_risky(self):
        tasks = [
            _make_task(task_id="a", safety_risk=True),
            _make_task(task_id="b", safety_risk=True),
        ]
        has_risky, ids = ClinicalAuditor.scan_safety_risk_tasks(tasks)
        assert has_risky is True
        assert set(ids) == {"a", "b"}

    def test_empty_list(self):
        has_risky, ids = ClinicalAuditor.scan_safety_risk_tasks([])
        assert has_risky is False
        assert ids == []


# ===================================================================
# 6. Emergency payload construction
# ===================================================================


class TestEmergencyPayload:
    def test_en_payload(self):
        a = ClinicalAuditor(locale="en")
        payload = a._build_emergency_payload()
        assert isinstance(payload, EmergencyPayload)
        assert payload.locale == "en"
        assert len(payload.hotlines) >= 2
        assert all(isinstance(h, HotlineResource) for h in payload.hotlines)

    def test_ar_payload(self):
        a = ClinicalAuditor(locale="ar")
        payload = a._build_emergency_payload()
        assert payload.locale == "ar"
        assert any("\u0600" <= c <= "\u06ff" for h in payload.hotlines for c in h.name)

    def test_emergency_payload_model(self):
        ep = EmergencyPayload(
            message="test",
            hotlines=[HotlineResource(name="Test", number="123", description="d")],
        )
        assert ep.message == "test"
        assert ep.immediate_action != ""


# ===================================================================
# 7. Full audit — GREEN path
# ===================================================================


class TestAuditGreen:
    def test_safe_text(self):
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap("Steps for managing stress."))
        assert result.safety_status == "GREEN"
        assert result.next_checkup_days == 14
        assert result.emergency_payload is None

    def test_safe_text_arabic_locale(self):
        a = ClinicalAuditor(locale="ar")
        result = a.audit(_make_roadmap("خطوات لإدارة التوتر"))
        assert result.safety_status == "GREEN"

    def test_empty_overview(self):
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap(""))
        assert result.safety_status == "GREEN"

    def test_empty_string_overview(self):
        a = ClinicalAuditor(locale="en")
        r = _make_roadmap("")
        result = a.audit(r)
        assert result.safety_status == "GREEN"

    def test_flags_empty_on_green(self):
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap("all good"))
        assert result.flags.crisis_detected is False
        assert result.flags.robotic_tone_detected is False
        assert result.flags.safety_risk_task_found is False


# ===================================================================
# 8. Full audit — RED path (crisis keywords)
# ===================================================================


class TestAuditRedCrisis:
    def test_english_crisis_keyword(self):
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap("I feel suicidal and need help."))
        assert result.safety_status == "RED"
        assert result.next_checkup_days == 1
        assert result.emergency_payload is not None
        assert result.flags.crisis_detected is True

    def test_arabic_crisis_keyword(self):
        a = ClinicalAuditor(locale="ar")
        result = a.audit(_make_roadmap("أريد الانتحار"))
        assert result.safety_status == "RED"
        assert result.emergency_payload is not None

    def test_red_overview_replaced(self):
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap("I want to end my life."))
        assert result.overview_paragraph == GUIDANCE_MESSAGES["en"]["red"]

    def test_red_overview_arabic(self):
        a = ClinicalAuditor(locale="ar")
        result = a.audit(_make_roadmap("أريد أن أموت"))
        assert result.overview_paragraph == GUIDANCE_MESSAGES["ar"]["red"]


# ===================================================================
# 9. Full audit — RED path (safety_risk task override)
# ===================================================================


class TestAuditRedSafetyRisk:
    def test_safety_risk_task_forces_red(self):
        """Even with safe text, a safety_risk=True task triggers RED."""
        a = ClinicalAuditor(locale="en")
        tasks = [_make_task(task_id="danger", safety_risk=True)]
        result = a.audit(_make_roadmap("All is well."), tasks=tasks)
        assert result.safety_status == "RED"
        assert result.flags.safety_risk_task_found is True
        assert "danger" in result.flags.safety_risk_task_ids

    def test_safety_risk_with_clean_text(self):
        a = ClinicalAuditor(locale="en")
        tasks = [_make_task(task_id="r1", safety_risk=True)]
        result = a.audit(_make_roadmap("Great day ahead!"), tasks=tasks)
        assert result.safety_status == "RED"

    def test_safety_risk_multiple_tasks(self):
        a = ClinicalAuditor(locale="en")
        tasks = [
            _make_task(task_id="safe", safety_risk=False),
            _make_task(task_id="risky", safety_risk=True),
        ]
        result = a.audit(_make_roadmap("nice"), tasks=tasks)
        assert result.safety_status == "RED"
        assert result.flags.safety_risk_task_ids == ["risky"]

    def test_safety_risk_no_tasks_provided(self):
        """When tasks=None, safety_risk scan is skipped."""
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap("nice"), tasks=None)
        assert result.safety_status == "GREEN"


# ===================================================================
# 10. Full audit — YELLOW path (robotic tone)
# ===================================================================


class TestAuditYellow:
    def test_robotic_tone(self):
        a = ClinicalAuditor(locale="en")
        result = a.audit(_make_roadmap("As an AI language model I cannot help."))
        assert result.safety_status == "YELLOW"
        assert result.next_checkup_days == 7
        assert result.flags.robotic_tone_detected is True

    def test_yellow_arabic_locale(self):
        a = ClinicalAuditor(locale="ar")
        result = a.audit(_make_roadmap("As an AI language model"))
        assert result.safety_status == "YELLOW"
        assert result.overview_paragraph == GUIDANCE_MESSAGES["ar"]["yellow"]


# ===================================================================
# 11. Priority: safety_risk > crisis > robotic > green
# ===================================================================


class TestAuditPriority:
    def test_safety_risk_overrides_crisis_in_text(self):
        """Safety-risk task should trigger RED even if no crisis text."""
        a = ClinicalAuditor(locale="en")
        tasks = [_make_task(task_id="x", safety_risk=True)]
        result = a.audit(_make_roadmap("peaceful day"), tasks=tasks)
        assert result.safety_status == "RED"

    def test_crisis_overrides_robotic(self):
        """Crisis should win over robotic tone."""
        a = ClinicalAuditor(locale="en")
        result = a.audit(
            _make_roadmap("As an AI, I feel suicidal and want to end my life.")
        )
        assert result.safety_status == "RED"


# ===================================================================
# 12. AuditResult schema
# ===================================================================


class TestAuditResultSchema:
    def test_full_green_result(self):
        r = AuditResult(
            safety_status="GREEN",
            next_checkup_days=14,
            overview_paragraph="test",
            task_ids=["t1"],
        )
        assert r.safety_status == "GREEN"
        assert r.emergency_payload is None

    def test_full_red_result(self):
        ep = EmergencyPayload(
            message="help",
            hotlines=[
                HotlineResource(name="911", number="911", description="emergency")
            ],
        )
        r = AuditResult(
            safety_status="RED",
            next_checkup_days=1,
            emergency_payload=ep,
            overview_paragraph="help",
            flags=AuditFlags(
                crisis_detected=True,
                crisis_keywords_found=["suicide"],
            ),
        )
        assert r.safety_status == "RED"
        assert r.emergency_payload.message == "help"


# ===================================================================
# 13. Backward compatibility: module-level audit_roadmap()
# ===================================================================


class TestBackwardCompatAuditRoadmap:
    def test_green_default_locale(self):
        r = _make_roadmap("wellness steps")
        out = audit_roadmap(r)
        assert out.safety_status == "GREEN"

    def test_red_crisis_keyword(self):
        r = _make_roadmap("I feel suicidal and need help.")
        out = audit_roadmap(r)
        assert out.safety_status == "RED"
        assert out.next_checkup_days == 1
        assert len(out.suggested_tasks) == 1
        assert out.suggested_tasks[0].task_id == "emergency_resources"

    def test_red_arabic_locale(self):
        r = _make_roadmap("أريد الانتحار")
        out = audit_roadmap(r, locale="ar")
        assert out.safety_status == "RED"

    def test_yellow_robotic(self):
        r = _make_roadmap("As an AI language model I cannot diagnose you.")
        out = audit_roadmap(r)
        assert out.safety_status == "YELLOW"

    def test_safety_risk_task_override(self):
        r = _make_roadmap("all good")
        tasks = [_make_task(task_id="d1", safety_risk=True)]
        out = audit_roadmap(r, tasks=tasks)
        assert out.safety_status == "RED"

    def test_yellow_arabic(self):
        r = _make_roadmap("As an AI language model")
        out = audit_roadmap(r, locale="ar")
        assert out.safety_status == "YELLOW"


# ===================================================================
# 14. Legacy import compatibility (from services.architect.auditor)
# ===================================================================


class TestLegacyImportCompat:
    def test_import_from_architect_auditor(self):
        from services.architect.auditor import (
            CRISIS_KEYWORDS_AR,
            CRISIS_KEYWORDS_EN,
            GUIDANCE_MESSAGES,
            ROBOTIC_TONE_KEYWORDS,
            audit_roadmap as legacy_audit,
        )

        r = _make_roadmap("safe content")
        out = legacy_audit(r)
        assert out.safety_status == "GREEN"

        assert len(CRISIS_KEYWORDS_EN) >= 10
        assert len(CRISIS_KEYWORDS_AR) >= 10

    def test_legacy_reexports_crisis_keywords(self):
        from services.architect.auditor import CRISIS_KEYWORDS_EN as old_en

        assert "suicide" in old_en


# ===================================================================
# 15. AuditRequest schema
# ===================================================================


class TestAuditRequestSchema:
    def test_minimal_request(self):
        req = AuditRequest(
            user_id="u1",
            overview_paragraph="test",
        )
        assert req.locale == "en"
        assert req.task_contents == []

    def test_full_request(self):
        req = AuditRequest(
            user_id="u2",
            overview_paragraph="crisis text",
            locale="ar",
            task_contents=[
                {
                    "task_id": "t1",
                    "content": "breathing",
                    "symptom_tags": ["anxiety"],
                    "difficulty": 1,
                    "xp_reward": 50,
                    "safety_risk": False,
                    "source_reference": "ref",
                }
            ],
        )
        assert req.locale == "ar"
        assert len(req.task_contents) == 1


# ===================================================================
# 16. apply_to_roadmap in-place mutation
# ===================================================================


class TestApplyToRoadmap:
    def test_green_no_mutation_of_status(self):
        a = ClinicalAuditor(locale="en")
        r = _make_roadmap("safe")
        result = a.apply_to_roadmap(r)
        assert result.safety_status == "GREEN"
        assert r.safety_status == "GREEN"

    def test_red_mutates_roadmap(self):
        a = ClinicalAuditor(locale="en")
        r = _make_roadmap("I want to die.")
        result = a.apply_to_roadmap(r)
        assert result.safety_status == "RED"
        assert r.safety_status == "RED"
        assert r.next_checkup_days == 1
        assert len(r.suggested_tasks) == 1
        assert r.suggested_tasks[0].task_id == "emergency_resources"

    def test_red_with_tasks(self):
        a = ClinicalAuditor(locale="en")
        tasks = [_make_task(task_id="r1", safety_risk=True)]
        r = _make_roadmap("safe", tasks=tasks)
        result = a.apply_to_roadmap(r, tasks=tasks)
        assert result.safety_status == "RED"
        assert len(result.suggested_tasks) == 1
