import pytest

from tests.fixtures.clinical_tasks import (
    SAMPLE_TASKS,
    SAFETY_EDGE_CASE_TASKS,
    FIXTURE_SCENARIO_MAP,
)


def test_sample_tasks_count() -> None:
    assert len(SAMPLE_TASKS) >= 10


def test_difficulty_range() -> None:
    for task in SAMPLE_TASKS:
        assert 1 <= task.difficulty <= 5


def test_symptom_tags_populated() -> None:
    for task in SAMPLE_TASKS:
        assert len(task.symptom_tags) > 0


def test_xp_reward_non_negative() -> None:
    for task in SAMPLE_TASKS:
        assert task.xp_reward >= 0


def test_safety_risk_top_level_field() -> None:
    for task in SAMPLE_TASKS:
        assert hasattr(task, "safety_risk")
        assert isinstance(task.safety_risk, bool)


def test_utility_score_top_level_field() -> None:
    for task in SAMPLE_TASKS:
        assert hasattr(task, "utility_score")
        assert isinstance(task.utility_score, float)
        assert 0.0 <= task.utility_score <= 1.0


def test_safety_edge_case_exists() -> None:
    safety_tasks = [t for t in SAFETY_EDGE_CASE_TASKS if t.safety_risk is True]
    assert len(safety_tasks) >= 1


def test_crisis_task_zero_xp() -> None:
    for task in SAFETY_EDGE_CASE_TASKS:
        if task.safety_risk:
            assert task.xp_reward == 0


def test_fixture_importable() -> None:
    from tests.fixtures.clinical_tasks import SAMPLE_TASKS as imported

    assert len(imported) >= 10


def test_scenario_mapping_complete() -> None:
    assert "anxiety-mild" in FIXTURE_SCENARIO_MAP
    assert "depression-moderate" in FIXTURE_SCENARIO_MAP
    assert "safety-audit" in FIXTURE_SCENARIO_MAP
    assert "difficulty-sweep" in FIXTURE_SCENARIO_MAP


def test_difficulty_sweep_covers_all_levels() -> None:
    sweep_ids = FIXTURE_SCENARIO_MAP["difficulty-sweep"]
    difficulties = {t.difficulty for t in SAMPLE_TASKS if t.task_id in sweep_ids}
    assert len(difficulties) >= 4
