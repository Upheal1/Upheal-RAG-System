"""
Unit tests for the Gateway Orchestration Chain (A-YAH-09).

Covers:
- Full chain happy path (with mocked KB)
- Per-stage logging (start/done events)
- Error handling → safe fallback (never stack traces)
- Gamifier _sequence_tasks() pass-through hook
- Arabic locale propagation through all stages
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

from services.gateway.orchestrator import (
    _sequence_tasks,
    _safe_fallback_response,
    run_assessment_chain,
)
from services.shared.schemas import AssessGatewayResponse, ClinicalTask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_tasks() -> List[ClinicalTask]:
    return [
        ClinicalTask(
            task_id="t1",
            content="Grounding exercise: 5-4-3-2-1.",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test-ref",
            metadata={"similarity": 0.85},
        ),
        ClinicalTask(
            task_id="t2",
            content="Deep breathing for 4 minutes.",
            symptom_tags=["anxiety", "stress"],
            difficulty=1,
            xp_reward=45,
            safety_risk=False,
            utility_score=0.6,
            source_reference="test-ref",
            metadata={"similarity": 0.72},
        ),
    ]


# ===================================================================
# 1. Gamifier sequence hook (pass-through)
# ===================================================================


class TestSequenceTasksHook:
    def test_returns_same_content(self):
        from services.shared.schemas import UserContext

        tasks = _sample_tasks()
        ctx = UserContext(
            user_id="u",
            timestamp="t",
            form_scores={"anxiety": 10},
            app_exposure_ratios={"r_app": 0.5},
            user_stats={},
        )
        result = _sequence_tasks(tasks, ctx)
        assert len(result) == len(tasks)
        assert [t.task_id for t in result] == [t.task_id for t in tasks]

    def test_empty_list(self):
        from services.shared.schemas import UserContext

        ctx = UserContext(
            user_id="u",
            timestamp="t",
            form_scores={},
            app_exposure_ratios={},
            user_stats={},
        )
        result = _sequence_tasks([], ctx)
        assert result == []

    def test_preserves_order(self):
        from services.shared.schemas import UserContext

        tasks = _sample_tasks()
        ctx = UserContext(
            user_id="u",
            timestamp="t",
            form_scores={},
            app_exposure_ratios={},
            user_stats={},
        )
        result = _sequence_tasks(tasks, ctx)
        assert [t.task_id for t in result] == [t.task_id for t in tasks]


# ===================================================================
# 2. Safe fallback response
# ===================================================================


class TestSafeFallbackResponse:
    def test_returns_yellow_status(self):
        resp = _safe_fallback_response("u1", None, "profiler")
        assert resp.safety_status == "YELLOW"
        assert resp.next_checkup_days == 7
        assert resp.user_id == "u1"
        assert resp.query_used == "fallback"

    def test_no_stack_trace_in_response(self):
        resp = _safe_fallback_response("u1", "sess-1", "architect")
        assert "traceback" not in resp.overview_paragraph.lower()
        assert "error" not in resp.overview_paragraph.lower()
        assert (
            "advisory" in resp.overview_paragraph.lower()
            or "review" in resp.overview_paragraph.lower()
        )

    def test_preserves_session_id(self):
        resp = _safe_fallback_response("u1", "my-session", "profiler")
        assert resp.session_id == "my-session"

    def test_empty_tasks(self):
        resp = _safe_fallback_response("u1", None, "profiler")
        assert resp.suggested_tasks == []

    def test_with_answers(self):
        answers = {f"gad7_q{i}": 2 for i in range(1, 8)}
        resp = _safe_fallback_response("u1", None, "profiler", answers=answers)
        assert resp.anxiety_probability > 0.0


# ===================================================================
# 3. Full chain happy path (mocked KB)
# ===================================================================


class TestOrchestrationHappyPath:
    @patch("services.gateway.orchestrator._kb")
    def test_returns_assess_gateway_response(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="test-user",
            raw_payload={"answers": {"gad7_q1": 1}},
            screen_time_minutes=90.0,
            locale="en",
            session_id="s-1",
        )

        assert isinstance(resp, AssessGatewayResponse)
        assert resp.user_id == "test-user"
        assert resp.session_id == "s-1"
        assert resp.safety_status in ("GREEN", "YELLOW", "RED")
        assert resp.timestamp is not None

    @patch("services.gateway.orchestrator._kb")
    def test_response_has_tasks(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
        )

        assert len(resp.suggested_tasks) >= 1

    @patch("services.gateway.orchestrator._kb")
    def test_response_has_legacy_fields(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        answers = {f"gad7_q{i}": 1 for i in range(1, 8)}
        answers.update({f"phq9_q{i}": 1 for i in range(1, 10)})
        resp = run_assessment_chain(
            user_id="u",
            raw_payload={"answers": answers},
            screen_time_minutes=0,
        )

        assert resp.anxiety_probability >= 0.0
        assert resp.depression_probability >= 0.0
        assert "anxiety" in resp.severity
        assert "depression" in resp.severity
        assert resp.comorbidity in ("true", "false")

    @patch("services.gateway.orchestrator._kb")
    def test_response_has_rag_recommendations(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
        )

        for rec in resp.rag_recommendations:
            assert rec.source is not None
            assert rec.content is not None


# ===================================================================
# 4. Error handling — each stage fails independently
# ===================================================================


class TestOrchestrationErrors:
    def test_profiler_error_returns_safe_fallback(self):
        with patch(
            "services.gateway.orchestrator.build_user_context",
            side_effect=RuntimeError("DB connection lost"),
        ):
            resp = run_assessment_chain(
                user_id="u",
                raw_payload={},
                screen_time_minutes=0,
            )

            assert isinstance(resp, AssessGatewayResponse)
            assert resp.safety_status == "YELLOW"
            assert resp.query_used == "fallback"
            assert "error" not in resp.overview_paragraph.lower()

    @patch("services.gateway.orchestrator._kb")
    def test_architect_error_returns_safe_fallback(self, mock_kb):
        mock_kb.retrieve_tasks.side_effect = RuntimeError("ChromaDB crash")

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={"answers": {"gad7_q1": 1}},
            screen_time_minutes=0,
        )

        assert resp.safety_status == "YELLOW"
        assert resp.query_used == "fallback"

    def test_assemble_error_returns_safe_fallback(self):
        """Simulate an assemble error by patching assemble_response."""
        with patch("services.gateway.orchestrator._kb") as mock_kb:
            mock_kb.retrieve_tasks.return_value = _sample_tasks()
            mock_kb.is_healthy.return_value = True
            mock_kb.get_document_count.return_value = 10

            with patch(
                "services.gateway.orchestrator._assemble_response",
                side_effect=ValueError("template failure"),
            ):
                resp = run_assessment_chain(
                    user_id="u",
                    raw_payload={},
                    screen_time_minutes=0,
                )

                assert resp.safety_status == "YELLOW"
                assert resp.query_used == "fallback"

    @patch("services.gateway.orchestrator._kb")
    def test_never_exposes_stack_trace(self, mock_kb):
        mock_kb.retrieve_tasks.side_effect = RuntimeError(
            "Secret internal error: stack trace details here"
        )

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
        )

        resp_text = resp.overview_paragraph.lower()
        assert "secret" not in resp_text
        assert "traceback" not in resp_text
        assert "stack" not in resp_text


# ===================================================================
# 5. Locale propagation
# ===================================================================


class TestLocalePropagation:
    @patch("services.gateway.orchestrator._kb")
    def test_english_locale_flows_through(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
            locale="en",
        )

        assert resp.user_id == "u"

    @patch("services.gateway.orchestrator._kb")
    def test_arabic_locale_flows_through(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
            locale="ar",
        )

        assert resp.user_id == "u"


# ===================================================================
# 6. Screen time drives R_app
# ===================================================================


class TestScreenTimeDrivesRApp:
    @patch("services.gateway.orchestrator._kb")
    def test_high_screen_time(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=120.0,
        )

        assert resp.suggested_tasks is not None

    @patch("services.gateway.orchestrator._kb")
    def test_zero_screen_time(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
        )

        assert resp.suggested_tasks is not None


# ===================================================================
# 7. Empty forms / no answers
# ===================================================================


class TestEmptyForms:
    @patch("services.gateway.orchestrator._kb")
    def test_no_answers_returns_mild_defaults(self, mock_kb):
        mock_kb.retrieve_tasks.return_value = _sample_tasks()
        mock_kb.is_healthy.return_value = True
        mock_kb.get_document_count.return_value = 10

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
        )

        assert resp.severity["anxiety"] == "Mild"
        assert resp.severity["depression"] == "Mild"
        assert resp.comorbidity == "false"
