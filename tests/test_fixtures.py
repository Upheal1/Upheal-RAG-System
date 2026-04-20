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


def test_safety_risk_in_metadata() -> None:
    for task in SAMPLE_TASKS:
        assert "safety_risk" in task.metadata


def test_utility_score_in_metadata() -> None:
    for task in SAMPLE_TASKS:
        assert "utility_score" in task.metadata


def test_safety_edge_case_exists() -> None:
    safety_tasks = [
        t for t in SAFETY_EDGE_CASE_TASKS if t.metadata.get("safety_risk") is True
    ]
    assert len(safety_tasks) >= 1


def test_crisis_task_zero_xp() -> None:
    for task in SAFETY_EDGE_CASE_TASKS:
        if task.metadata.get("safety_risk"):
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
