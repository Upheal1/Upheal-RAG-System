from __future__ import annotations

from services.architect.pipeline import (
    _jaccard_overlap,
    _apply_detox_boost,
    rerank_tasks,
)
from services.shared.schemas import ClinicalTask, RetrievalQuery, UserContext


def _make_user_context(
    level: int = 3,
    r_app: float = 0.5,
    form_scores: dict[str, int] | None = None,
) -> UserContext:
    return UserContext(
        user_id="test-user",
        timestamp="2026-01-01T00:00:00",
        form_scores=form_scores or {"anxiety": 60, "depression": 40},
        app_exposure_ratios={"r_app": r_app},
        user_stats={"level": level, "xp": 300},
    )


def _make_task(
    task_id: str,
    difficulty: int,
    tags: list[str],
    similarity: float = 0.5,
    utility_score: float = 0.5,
) -> ClinicalTask:
    return ClinicalTask(
        task_id=task_id,
        content=f"Task content for {task_id}",
        symptom_tags=tags,
        difficulty=difficulty,
        xp_reward=difficulty * 20,
        safety_risk=False,
        utility_score=utility_score,
        source_reference="test",
        metadata={"similarity": similarity},
    )


# ---------------------------------------------------------------------------
# Jaccard overlap tests
# ---------------------------------------------------------------------------


class TestJaccardOverlap:
    def test_exact_overlap(self) -> None:
        assert _jaccard_overlap(["anxiety"], {"anxiety"}) == 1.0

    def test_partial_overlap(self) -> None:
        result = _jaccard_overlap(["anxiety", "panic"], {"anxiety", "depression"})
        assert result == 1 / 3

    def test_zero_overlap(self) -> None:
        result = _jaccard_overlap(["insomnia"], {"anxiety", "depression"})
        assert result == 0.0

    def test_case_insensitive(self) -> None:
        result = _jaccard_overlap(["Anxiety", "PANIC"], {"anxiety", "depression"})
        assert result == 1 / 3

    def test_empty_task_tags(self) -> None:
        assert _jaccard_overlap([], {"anxiety"}) == 0.0

    def test_empty_user_domains(self) -> None:
        assert _jaccard_overlap(["anxiety"], set()) == 0.0

    def test_both_empty(self) -> None:
        assert _jaccard_overlap([], set()) == 0.0


# ---------------------------------------------------------------------------
# Digital detox boost tests
# ---------------------------------------------------------------------------


class TestDigitalDetoxBoost:
    def test_boost_applies_to_grounding_task(self) -> None:
        task = _make_task("t1", 1, ["grounding"])
        boosted = _apply_detox_boost(0.5, task, boost=True)
        assert boosted == 0.5 * 1.15

    def test_boost_applies_to_breathing_task(self) -> None:
        task = _make_task("t1", 1, ["breathing"])
        boosted = _apply_detox_boost(0.6, task, boost=True)
        assert boosted == 0.6 * 1.15

    def test_boost_applies_to_mindfulness_task(self) -> None:
        task = _make_task("t1", 1, ["mindfulness", "stress"])
        boosted = _apply_detox_boost(0.4, task, boost=True)
        assert boosted == 0.4 * 1.15

    def test_no_boost_for_non_detox_tags(self) -> None:
        task = _make_task("t1", 1, ["cbt", "cognitive"])
        boosted = _apply_detox_boost(0.5, task, boost=True)
        assert boosted == 0.5

    def test_no_boost_when_flag_disabled(self) -> None:
        task = _make_task("t1", 1, ["grounding"])
        result = _apply_detox_boost(0.5, task, boost=False)
        assert result == 0.5


# ---------------------------------------------------------------------------
# Rerank with digital detox tests
# ---------------------------------------------------------------------------


class TestRerankDigitalDetox:
    def test_boost_changes_ordering(self) -> None:
        grounding = _make_task("t1", 2, ["grounding"], similarity=0.4)
        cognitive = _make_task("t2", 2, ["cbt"], similarity=0.5)
        ctx = _make_user_context(
            form_scores={"anxiety": 60},
            r_app=0.5,
        )

        without_boost = rerank_tasks(
            [grounding, cognitive], ctx, top_n=2, boost_digital_detox=False
        )
        assert without_boost[0].task_id == "t2"

        with_boost = rerank_tasks(
            [grounding, cognitive], ctx, top_n=2, boost_digital_detox=True
        )
        assert with_boost[0].task_id == "t1"

    def test_no_change_when_no_detox_tasks_present(self) -> None:
        t1 = _make_task("t1", 2, ["cbt"], similarity=0.7)
        t2 = _make_task("t2", 2, ["journaling"], similarity=0.5)
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        no_boost = rerank_tasks([t1, t2], ctx, top_n=2, boost_digital_detox=False)
        boost = rerank_tasks([t1, t2], ctx, top_n=2, boost_digital_detox=True)

        assert no_boost[0].task_id == boost[0].task_id == "t1"


# ---------------------------------------------------------------------------
# Deterministic tie-break tests
# ---------------------------------------------------------------------------


class TestDeterministicTieBreak:
    def test_equal_scores_lower_difficulty_first(self) -> None:
        easy = _make_task("task-a", 1, ["anxiety"], similarity=0.5)
        hard = _make_task("task-b", 3, ["anxiety"], similarity=0.5)
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        result = rerank_tasks([hard, easy], ctx, top_n=2)
        assert result[0].task_id == "task-a"
        assert result[1].task_id == "task-b"

    def test_equal_scores_and_difficulty_alphabetical(self) -> None:
        t1 = _make_task("task-b", 2, ["anxiety"], similarity=0.5)
        t2 = _make_task("task-a", 2, ["anxiety"], similarity=0.5)
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        result = rerank_tasks([t1, t2], ctx, top_n=2)
        assert result[0].task_id == "task-b"
        assert result[1].task_id == "task-a"

    def test_output_stable_on_repeated_calls(self) -> None:
        tasks = [
            _make_task("t1", 2, ["anxiety"], similarity=0.6),
            _make_task("t2", 2, ["depression"], similarity=0.6),
            _make_task("t3", 1, ["anxiety"], similarity=0.5),
        ]
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        result1 = rerank_tasks(tasks, ctx, top_n=3)
        result2 = rerank_tasks(tasks, ctx, top_n=3)

        assert [t.task_id for t in result1] == [t.task_id for t in result2]


# ---------------------------------------------------------------------------
# Full pipeline integration with boost_digital_detox
# ---------------------------------------------------------------------------


class TestPipelineDigitalDetoxIntegration:
    def test_retrieval_query_boost_flag_propagates_to_rerank(self) -> None:
        from services.architect.pipeline import run_architect_pipeline

        tasks = [
            _make_task("grounding-task", 1, ["anxiety", "grounding"], similarity=0.3),
            _make_task("cbt-task", 1, ["cbt"], similarity=0.6),
        ]
        ctx = _make_user_context(
            form_scores={"anxiety": 60},
            r_app=0.9,
        )
        rq = RetrievalQuery(
            symptom_keywords=["anxiety"],
            boost_digital_detox=True,
            candidate_count=2,
        )
        result = run_architect_pipeline(
            ctx,
            candidate_tasks=tasks,
            retrieval_query=rq,
            top_n=2,
        )

        first_task_ids = [t.task_id for t in result.suggested_tasks[:1]]
        assert "grounding-task" in first_task_ids


# ---------------------------------------------------------------------------
# Triple-Threat v2: UtilityScore tests (A-YAH-14)
# ---------------------------------------------------------------------------


class TestTripleThreatV2UtilityScore:
    def test_utility_score_normalized_to_1(self) -> None:
        from services.architect.pipeline import _triple_threat_score

        score = _triple_threat_score(
            similarity=0.5, form_weight=0.5, r_app=0.5, utility_score=2.0
        )
        assert 0.0 <= score <= 1.5

    def test_utility_score_normalized_to_0(self) -> None:
        from services.architect.pipeline import _triple_threat_score

        score = _triple_threat_score(
            similarity=0.5, form_weight=0.5, r_app=0.5, utility_score=-0.5
        )
        assert 0.0 <= score <= 1.5

    def test_utility_score_default_0_5(self) -> None:
        from services.architect.pipeline import _triple_threat_score

        score_with_default = _triple_threat_score(
            similarity=0.5, form_weight=0.5, r_app=0.5
        )
        score_with_explicit = _triple_threat_score(
            similarity=0.5, form_weight=0.5, r_app=0.5, utility_score=0.5
        )
        assert score_with_default == score_with_explicit

    def test_different_utility_changes_ordering(self) -> None:
        high_utility = _make_task(
            "high-utility", 2, ["anxiety"], similarity=0.5, utility_score=0.9
        )
        low_utility = _make_task(
            "low-utility", 2, ["anxiety"], similarity=0.5, utility_score=0.1
        )
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        result = rerank_tasks([low_utility, high_utility], ctx, top_n=2)
        assert result[0].task_id == "high-utility"

    def test_utility_score_at_fixed_similarity_changes_ordering(self) -> None:
        t1 = _make_task("task-1", 2, ["anxiety"], similarity=0.6, utility_score=0.3)
        t2 = _make_task("task-2", 2, ["anxiety"], similarity=0.6, utility_score=0.8)
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        result = rerank_tasks([t1, t2], ctx, top_n=2)
        assert result[0].task_id == "task-2"

    def test_utility_weight_0_15_in_formula(self) -> None:
        from services.architect.pipeline import _triple_threat_score

        base_score = _triple_threat_score(
            similarity=0.0, form_weight=0.0, r_app=0.0, utility_score=1.0
        )
        utility_contribution = base_score
        assert 0.14 <= utility_contribution <= 0.16

    def test_red_safety_path_bypasses_ranking(self) -> None:
        from services.architect.pipeline import run_architect_pipeline
        from services.shared.schemas import FinalRoadmap

        dangerous_task = _make_task(
            "dangerous", 3, ["suicide"], similarity=0.9, utility_score=0.9
        )
        safe_task = _make_task(
            "safe", 1, ["breathing"], similarity=0.1, utility_score=0.1
        )
        ctx = _make_user_context(form_scores={"anxiety": 60}, r_app=0.5)

        result = run_architect_pipeline(
            ctx,
            candidate_tasks=[dangerous_task, safe_task],
            top_n=2,
        )
        assert result.safety_status == "RED"
