"""
Unit tests for 90-day roadmap schemas (Task 2A).
"""

import pytest
from pydantic import ValidationError

from services.gateway.schemas import RoadmapRequest, RoadmapResponse
from services.shared.schemas import ClinicalTask, ReassessmentStatus, RoadmapDay


class TestRoadmapDay:
    def test_valid_day(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=2,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        day = RoadmapDay(
            day_number=1,
            task=task,
            phase="Quick Win",
            day_context="morning routine",
        )
        assert day.day_number == 1
        assert day.phase == "Quick Win"
        assert day.day_context == "morning routine"

    def test_day_number_min(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        day = RoadmapDay(day_number=1, task=task, phase="Quick Win")
        assert day.day_number == 1

    def test_day_number_max(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=5,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        day = RoadmapDay(day_number=90, task=task, phase="Boss")
        assert day.day_number == 90

    def test_invalid_day_number_too_low(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        with pytest.raises(ValidationError):
            RoadmapDay(day_number=0, task=task, phase="Quick Win")

    def test_invalid_day_number_too_high(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        with pytest.raises(ValidationError):
            RoadmapDay(day_number=91, task=task, phase="Quick Win")

    def test_all_phases(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        for phase in ["Quick Win", "Ladder", "Boss"]:
            day = RoadmapDay(day_number=1, task=task, phase=phase)
            assert day.phase == phase


class TestReassessmentStatus:
    def test_full_status(self) -> None:
        status = ReassessmentStatus(
            user_id="user-123",
            roadmap_id="roadmap-456",
            roadmap_status="ACTIVE",
            current_day=45,
            total_days=90,
            assessment_required=False,
            days_since_last_assessment=45,
        )
        assert status.user_id == "user-123"
        assert status.roadmap_status == "ACTIVE"
        assert status.current_day == 45
        assert status.assessment_required is False

    def test_no_roadmap(self) -> None:
        status = ReassessmentStatus(
            user_id="user-123",
            assessment_required=True,
        )
        assert status.roadmap_id is None
        assert status.assessment_required is True

    def test_defaults(self) -> None:
        status = ReassessmentStatus(user_id="user-123")
        assert status.total_days == 90
        assert status.assessment_required is False
        assert status.current_day is None


class TestRoadmapResponse:
    def test_with_90_day_roadmap(self) -> None:
        task = ClinicalTask(
            task_id="t-1",
            content="Test task",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        days = [
            RoadmapDay(
                day_number=i,
                task=task,
                phase="Quick Win",
                day_context="morning routine",
            )
            for i in range(1, 8)
        ]
        response = RoadmapResponse(
            user_id="user-123",
            overview_paragraph="Test roadmap",
            suggested_tasks=[task],
            safety_status="GREEN",
            next_checkup_days=7,
            generated_at="2026-05-12T00:00:00Z",
            days=days,
            total_days=90,
            assessment_required=False,
        )
        assert len(response.days) == 7
        assert response.total_days == 90
        assert response.assessment_required is False

    def test_empty_days_default(self) -> None:
        response = RoadmapResponse(
            user_id="user-123",
            overview_paragraph="Test",
            suggested_tasks=[],
            safety_status="GREEN",
            next_checkup_days=7,
            generated_at="2026-05-12T00:00:00Z",
        )
        assert response.days == []
        assert response.total_days == 90
        assert response.assessment_required is False


class TestRoadmapRequest:
    def test_valid_request(self) -> None:
        req = RoadmapRequest(
            user_id="user-123",
            answers={"gad7_q1": 2, "phq9_q1": 1},
            top_n=5,
        )
        assert req.user_id == "user-123"
        assert req.top_n == 5

    def test_top_n_bounds(self) -> None:
        req = RoadmapRequest(user_id="user", top_n=10)
        assert req.top_n == 10

        with pytest.raises(ValidationError):
            RoadmapRequest(user_id="user", top_n=0)

        with pytest.raises(ValidationError):
            RoadmapRequest(user_id="user", top_n=11)
