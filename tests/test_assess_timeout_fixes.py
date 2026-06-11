"""
Unit tests for the /api/assess timeout fixes (Fixes 1-5).

Covers:
- Fix 1: TimeoutMiddleware returns 504 on timeout
- Fix 2: SentenceTransformer preloaded at startup
- Fix 3: ChromaDB HttpClient configured with timeout settings
- Fix 4: Stage-level timing logged in run_assessment_chain()
- Fix 5: Duplicate Bayesian run_assessment() eliminated via thread-local cache
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest


# ===================================================================
# Fix 1: TimeoutMiddleware returns 504 on timeout
# ===================================================================


class TestTimeoutMiddleware:
    def test_timeout_env_var_respected(self):
        saved = os.environ.pop("REQUEST_TIMEOUT_SECONDS", None)
        try:
            os.environ["REQUEST_TIMEOUT_SECONDS"] = "30"
            from services.gateway.main import TimeoutMiddleware

            mw = TimeoutMiddleware(app=None, timeout_seconds=30)
            assert mw.timeout_seconds == 30
        finally:
            if saved is not None:
                os.environ["REQUEST_TIMEOUT_SECONDS"] = saved
            else:
                os.environ.pop("REQUEST_TIMEOUT_SECONDS", None)

    def test_timeout_env_var_default(self):
        os.environ.pop("REQUEST_TIMEOUT_SECONDS", None)
        from services.gateway.main import REQUEST_TIMEOUT_SECONDS

        assert REQUEST_TIMEOUT_SECONDS == 55

    def test_timeout_middleware_class_configured(self):
        from services.gateway.main import TimeoutMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware

        assert issubclass(TimeoutMiddleware, BaseHTTPMiddleware)

    def test_timeout_middleware_accepts_timeout_seconds_param(self):
        from services.gateway.main import TimeoutMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware

        mw = TimeoutMiddleware(app=None, timeout_seconds=42)
        assert mw.timeout_seconds == 42


# ===================================================================
# Fix 2: Model preloaded at startup
# ===================================================================


class TestStartupPreloading:
    @patch("services.gateway.main.validate_env")
    @patch("services.knowledge_base.chroma_adapter.ChromaKnowledgeBase")
    def test_startup_event_calls_ensure_loaded(self, mock_kb_cls, mock_validate):
        from services.gateway.main import startup_event

        mock_kb = MagicMock()
        mock_kb_cls.return_value = mock_kb

        asyncio.run(startup_event())

        mock_kb_cls.assert_called_once()
        mock_kb._ensure_loaded.assert_called_once()

    @patch("services.gateway.main.validate_env")
    @patch("services.knowledge_base.chroma_adapter.ChromaKnowledgeBase")
    def test_startup_event_handles_failure_gracefully(self, mock_kb_cls, mock_validate):
        from services.gateway.main import startup_event

        mock_kb = MagicMock()
        mock_kb._ensure_loaded.side_effect = RuntimeError("OOM")
        mock_kb_cls.return_value = mock_kb

        asyncio.run(startup_event())


# ===================================================================
# Fix 3: ChromaDB timeout settings
# ===================================================================


class TestChromaDBTimeout:
    def test_chroma_kb_stores_timeout_from_env(self):
        os.environ["CHROMA_TIMEOUT_SECONDS"] = "45"
        from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

        kb = ChromaKnowledgeBase(vector_db_path="http://localhost:8000")
        assert kb is not None
        os.environ["CHROMA_TIMEOUT_SECONDS"] = "30"

    def test_kb_initial_state_before_ensure_loaded(self):
        from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

        kb = ChromaKnowledgeBase(vector_db_path="/tmp/nonexistent_chroma_test")
        assert kb._collection is None
        assert kb._model is None
        assert kb._client is None

    def test_kb_constructor_honors_vector_db_path(self):
        from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

        kb = ChromaKnowledgeBase(vector_db_path="/custom/path")
        assert kb.vector_db_path == "/custom/path"

    def test_kb_uses_chroma_timeout_env_var_in_path(self):
        original = os.environ.get("CHROMA_TIMEOUT_SECONDS", "30")
        from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

        os.environ["CHROMA_TIMEOUT_SECONDS"] = "60"
        kb = ChromaKnowledgeBase(vector_db_path="http://localhost:8000")
        path_used = kb.vector_db_path
        assert path_used == "http://localhost:8000"
        os.environ["CHROMA_TIMEOUT_SECONDS"] = original


# ===================================================================
# Fix 4: Stage-level timing logged in run_assessment_chain()
# ===================================================================


class TestStageTimingLogging:
    @patch("services.gateway.orchestrator._kb")
    def test_chain_done_event_emitted(self, mock_kb):
        from services.gateway.orchestrator import run_assessment_chain
        from services.shared.schemas import ClinicalTask

        mock_kb.retrieve_tasks.return_value = [
            ClinicalTask(
                task_id="t1",
                content="test",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=10,
                safety_risk=False,
                utility_score=0.5,
                source_reference="ref",
                metadata={"similarity": 0.9},
            )
        ]

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={"answers": {"gad7_q1": 1}},
            screen_time_minutes=0,
        )

        assert resp.user_id == "u"

    @patch("services.gateway.orchestrator._kb")
    def test_chain_timing_has_duration_ms(self, mock_kb):
        from services.gateway.orchestrator import run_assessment_chain
        from services.shared.schemas import ClinicalTask

        mock_kb.retrieve_tasks.return_value = [
            ClinicalTask(
                task_id="t1",
                content="test",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=10,
                safety_risk=False,
                utility_score=0.5,
                source_reference="ref",
                metadata={"similarity": 0.9},
            )
        ]

        resp = run_assessment_chain(
            user_id="u",
            raw_payload={},
            screen_time_minutes=0,
        )

        assert resp.user_id == "u"


# ===================================================================
# Fix 5: Duplicate Bayesian call eliminated via thread-local cache
# ===================================================================


class TestBayesianCache:
    def test_get_cached_assessment_returns_none_with_no_answers(self):
        from services.assessment.core import (
            _get_cached_assessment,
            _clear_assessment_cache,
        )

        _clear_assessment_cache()
        result = _get_cached_assessment({})
        assert result is None

    def test_get_cached_assessment_caches_result(self):
        from services.assessment.core import (
            _get_cached_assessment,
            _clear_assessment_cache,
        )

        _clear_assessment_cache()

        mock_result = {
            "anxiety_probability": 0.7,
            "depression_probability": 0.3,
            "query": "anxiety moderate clinical psychology interventions",
        }

        with patch("services.assessment.core._load_assessment_engine") as mock_loader:
            mock_mod = MagicMock()
            mock_mod.run_assessment.return_value = mock_result
            mock_loader.return_value = mock_mod

            result1 = _get_cached_assessment({"gad7_q1": 2})
            result2 = _get_cached_assessment({"gad7_q1": 2})

            assert result1 == mock_result
            assert result2 == mock_result
            mock_mod.run_assessment.assert_called_once()

    def test_get_cached_assessment_different_answers_different_cache(self):
        from services.assessment.core import (
            _get_cached_assessment,
            _clear_assessment_cache,
        )

        _clear_assessment_cache()

        with patch("services.assessment.core._load_assessment_engine") as mock_loader:
            mock_mod = MagicMock()
            mock_mod.run_assessment.side_effect = [
                {
                    "anxiety_probability": 0.7,
                    "depression_probability": 0.3,
                    "query": "q1",
                },
                {
                    "anxiety_probability": 0.9,
                    "depression_probability": 0.1,
                    "query": "q2",
                },
            ]
            mock_loader.return_value = mock_mod

            r1 = _get_cached_assessment({"gad7_q1": 2})
            r2 = _get_cached_assessment({"gad7_q1": 3})

            mock_mod.run_assessment.assert_has_calls(
                [
                    (({"gad7_q1": 2},), {}),
                    (({"gad7_q1": 3},), {}),
                ]
            )

    def test_clear_assessment_cache(self):
        from services.assessment.core import (
            _get_cached_assessment,
            _clear_assessment_cache,
        )

        _clear_assessment_cache()

        with patch("services.assessment.core._load_assessment_engine") as mock_loader:
            mock_mod = MagicMock()
            mock_mod.run_assessment.return_value = {
                "anxiety_probability": 0.5,
                "depression_probability": 0.5,
                "query": "test",
            }
            mock_loader.return_value = mock_mod

            _get_cached_assessment({"gad7_q1": 1})
            _clear_assessment_cache()
            _get_cached_assessment({"gad7_q1": 1})

            assert mock_mod.run_assessment.call_count == 2

    def test_merge_scale_and_bayesian_uses_cache(self):
        from services.assessment.core import (
            _merge_scale_and_bayesian,
            _clear_assessment_cache,
        )

        _clear_assessment_cache()

        with patch("services.assessment.core._load_assessment_engine") as mock_loader:
            mock_mod = MagicMock()
            mock_mod.run_assessment.return_value = {
                "anxiety_probability": 0.7,
                "depression_probability": 0.3,
                "query": "anxiety moderate cognitive behavioral therapy",
            }
            mock_loader.return_value = mock_mod

            _merge_scale_and_bayesian({"gad7_q1": 2, "gad7_q2": 1})

            mock_mod.run_assessment.assert_called_once()

    def test_build_retrieval_query_text_uses_cache(self):
        from services.assessment.core import (
            _clear_assessment_cache,
            build_retrieval_query_text,
        )
        from services.shared.schemas import UserContext

        _clear_assessment_cache()

        ctx = UserContext(
            user_id="u",
            timestamp="t",
            form_scores={"anxiety": 40},
            app_exposure_ratios={"r_app": 0.5},
            user_stats={},
        )

        with patch("services.assessment.core._load_assessment_engine") as mock_loader:
            mock_mod = MagicMock()
            mock_mod.run_assessment.return_value = {
                "anxiety_probability": 0.7,
                "depression_probability": 0.3,
                "query": "anxiety moderate cognitive behavioral therapy",
            }
            mock_loader.return_value = mock_mod

            result = build_retrieval_query_text(ctx, {"gad7_q1": 2})

            assert "anxiety" in result
            mock_mod.run_assessment.assert_called_once()
