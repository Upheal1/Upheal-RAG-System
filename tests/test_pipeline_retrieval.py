from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.architect.pipeline import (
    _apply_difficulty_filter,
    _apply_symptom_overlap_filter,
    retrieve_candidates,
    run_architect_pipeline,
)
from services.shared.schemas import (
    ClinicalTask,
    RetrievalQuery,
    UserContext,
)


def _make_user_context(level: int = 3, r_app: float = 0.5) -> UserContext:
    return UserContext(
        user_id="test-user",
        timestamp="2026-01-01T00:00:00",
        form_scores={"anxiety": 60, "depression": 40},
        app_exposure_ratios={"r_app": r_app},
        user_stats={"level": level, "xp": 300},
    )


def _make_task(task_id: str, difficulty: int, tags: list[str]) -> ClinicalTask:
    return ClinicalTask(
        task_id=task_id,
        content=f"Task content for {task_id}",
        symptom_tags=tags,
        difficulty=difficulty,
        xp_reward=difficulty * 20,
        source_reference="test",
        metadata={"similarity": 0.5},
    )


# ---------------------------------------------------------------------------
# Difficulty filter tests
# ---------------------------------------------------------------------------


class TestDifficultyFilter:
    def test_filters_tasks_above_user_level(self) -> None:
        tasks = [
            _make_task("t1", 1, ["anxiety"]),
            _make_task("t2", 2, ["anxiety"]),
            _make_task("t3", 3, ["anxiety"]),
            _make_task("t4", 4, ["anxiety"]),
            _make_task("t5", 5, ["anxiety"]),
        ]
        result = _apply_difficulty_filter(tasks, max_difficulty=5, user_level=2)
        assert len(result) == 2
        assert {t.task_id for t in result} == {"t1", "t2"}

    def test_respects_max_difficulty_below_user_level(self) -> None:
        tasks = [
            _make_task("t1", 1, ["anxiety"]),
            _make_task("t2", 2, ["anxiety"]),
            _make_task("t3", 3, ["anxiety"]),
        ]
        result = _apply_difficulty_filter(tasks, max_difficulty=2, user_level=4)
        assert len(result) == 2
        assert {t.task_id for t in result} == {"t1", "t2"}

    def test_no_filter_when_all_within_range(self) -> None:
        tasks = [
            _make_task("t1", 1, ["anxiety"]),
            _make_task("t2", 2, ["anxiety"]),
        ]
        result = _apply_difficulty_filter(tasks, max_difficulty=5, user_level=5)
        assert len(result) == 2

    def test_returns_empty_when_none_qualify(self) -> None:
        tasks = [_make_task("t1", 5, ["anxiety"])]
        result = _apply_difficulty_filter(tasks, max_difficulty=2, user_level=1)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Symptom overlap filter tests
# ---------------------------------------------------------------------------


class TestSymptomOverlapFilter:
    def test_keeps_tasks_with_matching_tags(self) -> None:
        tasks = [
            _make_task("t1", 1, ["anxiety", "panic"]),
            _make_task("t2", 2, ["depression"]),
            _make_task("t3", 1, ["anxiety", "stress"]),
        ]
        result = _apply_symptom_overlap_filter(tasks, ["anxiety"])
        assert len(result) == 2
        assert {t.task_id for t in result} == {"t1", "t3"}

    def test_case_insensitive_matching(self) -> None:
        tasks = [
            _make_task("t1", 1, ["Anxiety", "Panic"]),
            _make_task("t2", 2, ["depression"]),
        ]
        result = _apply_symptom_overlap_filter(tasks, ["ANXIETY"])
        assert len(result) == 1
        assert result[0].task_id == "t1"

    def test_returns_all_when_no_keywords_provided(self) -> None:
        tasks = [
            _make_task("t1", 1, ["anxiety"]),
            _make_task("t2", 2, ["depression"]),
        ]
        result = _apply_symptom_overlap_filter(tasks, [])
        assert len(result) == 2

    def test_no_match_returns_empty(self) -> None:
        tasks = [
            _make_task("t1", 1, ["anxiety"]),
            _make_task("t2", 2, ["depression"]),
        ]
        result = _apply_symptom_overlap_filter(tasks, ["insomnia"])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# retrieve_candidates() tests
# ---------------------------------------------------------------------------


class TestRetrieveCandidates:
    def test_fixture_fallback_when_chroma_none(self) -> None:
        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(symptom_keywords=["anxiety"], candidate_count=5)
        result = retrieve_candidates(ctx, rq, chroma_kb=None)
        assert len(result) > 0

    def test_fixture_fallback_when_chroma_unhealthy(self) -> None:
        mock_kb = MagicMock()
        mock_kb.is_healthy.return_value = False
        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(symptom_keywords=["anxiety"], candidate_count=5)
        result = retrieve_candidates(ctx, rq, chroma_kb=mock_kb)
        assert len(result) > 0
        mock_kb.retrieve_tasks.assert_not_called()

    def test_uses_chroma_when_healthy(self) -> None:
        mock_task = ClinicalTask(
            task_id="chroma-1",
            content="Chroma task",
            symptom_tags=["anxiety"],
            difficulty=2,
            xp_reward=40,
            source_reference="chroma",
            metadata={"similarity": 0.8},
        )
        mock_kb = MagicMock()
        mock_kb.is_healthy.return_value = True
        mock_kb.retrieve_tasks.return_value = [mock_task]

        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(
            symptom_keywords=["anxiety"],
            candidate_count=5,
            max_difficulty=3,
        )
        result = retrieve_candidates(ctx, rq, chroma_kb=mock_kb)
        mock_kb.retrieve_tasks.assert_called_once()
        assert len(result) == 1
        assert result[0].task_id == "chroma-1"

    def test_applies_difficulty_filter_after_chroma_fetch(self) -> None:
        tasks = [
            ClinicalTask(
                task_id="easy",
                content="easy",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=20,
                source_reference="test",
                metadata={"similarity": 0.5},
            ),
            ClinicalTask(
                task_id="hard",
                content="hard",
                symptom_tags=["anxiety"],
                difficulty=5,
                xp_reward=100,
                source_reference="test",
                metadata={"similarity": 0.5},
            ),
        ]
        mock_kb = MagicMock()
        mock_kb.is_healthy.return_value = True
        mock_kb.retrieve_tasks.return_value = tasks

        ctx = _make_user_context(level=1)
        rq = RetrievalQuery(
            symptom_keywords=["anxiety"],
            candidate_count=10,
            max_difficulty=5,
        )
        result = retrieve_candidates(ctx, rq, chroma_kb=mock_kb)
        assert len(result) == 1
        assert result[0].task_id == "easy"

    def test_applies_symptom_overlap_filter_after_chroma_fetch(self) -> None:
        tasks = [
            ClinicalTask(
                task_id="match",
                content="match",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=20,
                source_reference="test",
                metadata={"similarity": 0.5},
            ),
            ClinicalTask(
                task_id="nomatch",
                content="nomatch",
                symptom_tags=["insomnia"],
                difficulty=1,
                xp_reward=20,
                source_reference="test",
                metadata={"similarity": 0.5},
            ),
        ]
        mock_kb = MagicMock()
        mock_kb.is_healthy.return_value = True
        mock_kb.retrieve_tasks.return_value = tasks

        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(
            symptom_keywords=["anxiety"],
            candidate_count=10,
            max_difficulty=5,
        )
        result = retrieve_candidates(ctx, rq, chroma_kb=mock_kb)
        assert len(result) == 1
        assert result[0].task_id == "match"

    def test_default_candidate_count_is_10(self) -> None:
        rq = RetrievalQuery()
        assert rq.candidate_count == 10

    def test_respects_custom_candidate_count(self) -> None:
        ctx = _make_user_context(level=5)
        rq = RetrievalQuery(candidate_count=3)
        result = retrieve_candidates(ctx, rq, chroma_kb=None)
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# run_architect_pipeline integration tests
# ---------------------------------------------------------------------------


class TestRunArchitectPipeline:
    def test_pipeline_with_candidate_tasks_directly(self) -> None:
        ctx = _make_user_context(level=3)
        tasks = [
            ClinicalTask(
                task_id="t1",
                content="task one",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=50,
                source_reference="test",
                metadata={"similarity": 0.8},
            ),
            ClinicalTask(
                task_id="t2",
                content="task two",
                symptom_tags=["depression"],
                difficulty=2,
                xp_reward=60,
                source_reference="test",
                metadata={"similarity": 0.6},
            ),
        ]
        result = run_architect_pipeline(ctx, candidate_tasks=tasks, top_n=2)
        assert result.user_id == "test-user"
        assert len(result.suggested_tasks) <= 2
        assert result.safety_status in ("GREEN", "YELLOW", "RED")

    def test_pipeline_uses_fixture_fallback_without_candidate_tasks_or_kb(self) -> None:
        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(symptom_keywords=["anxiety"], candidate_count=5)
        result = run_architect_pipeline(
            ctx,
            candidate_tasks=None,
            retrieval_query=rq,
            chroma_kb=None,
            top_n=3,
        )
        assert result.user_id == "test-user"
        assert len(result.suggested_tasks) <= 3

    def test_pipeline_with_chroma_kb(self) -> None:
        mock_task = ClinicalTask(
            task_id="chroma-pipeline",
            content="from chroma",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=30,
            source_reference="chroma",
            metadata={"similarity": 0.7},
        )
        mock_kb = MagicMock()
        mock_kb.is_healthy.return_value = True
        mock_kb.retrieve_tasks.return_value = [mock_task]

        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(symptom_keywords=["anxiety"], candidate_count=5)
        result = run_architect_pipeline(
            ctx,
            candidate_tasks=None,
            retrieval_query=rq,
            chroma_kb=mock_kb,
            top_n=1,
        )
        assert len(result.suggested_tasks) == 1
        assert result.suggested_tasks[0].task_id == "chroma-pipeline"

    def test_pipeline_uses_retrieval_query_locale_for_auditor(self) -> None:
        mock_task = ClinicalTask(
            task_id="t1",
            content="task one",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            source_reference="test",
            metadata={"similarity": 0.8},
        )
        ctx = _make_user_context(level=3)
        rq = RetrievalQuery(symptom_keywords=["anxiety"], locale="ar")
        result = run_architect_pipeline(
            ctx,
            candidate_tasks=[mock_task],
            retrieval_query=rq,
            top_n=1,
        )
        assert result is not None
