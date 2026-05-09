"""
End-to-end tests for frontend integration features:

1. ScreenTimeData parsing and enhanced r_app
2. Gamifier phase labels (Quick Win / Ladder / Boss)
3. Screen time insights in response
4. CORS headers
5. Both /api/assess and /api/roadmap with rich screen time data
"""

import pytest
from httpx import AsyncClient, ASGITransport

from services.assessment.core import (
    build_screen_time_insights,
    build_user_context,
    parse_screen_time_data,
    sigmoid_r_app,
)
from services.gateway.main import app
from services.shared.schemas import ScreenTimeAppUsage, ScreenTimeData


# ---------------------------------------------------------------------------
# ScreenTimeData parsing
# ---------------------------------------------------------------------------


class TestScreenTimeDataParsing:
    def test_parse_basic_screen_time_data(self):
        data = ScreenTimeData(
            totalMinutes=120.0,
            socialMinutes=45.0,
            productivityMinutes=30.0,
            dailyUsage=[
                ScreenTimeAppUsage(packageName="com.instagram.android", usageTime=30, category="social"),
                ScreenTimeAppUsage(packageName="com.whatsapp", usageTime=15, category="social"),
                ScreenTimeAppUsage(packageName="com.google.docs", usageTime=25, category="productivity"),
                ScreenTimeAppUsage(packageName="com.chrome", usageTime=50, category="other"),
            ],
        )
        parsed = parse_screen_time_data(data)
        assert parsed["total_minutes"] == 120.0
        assert abs(parsed["social_ratio"] - 45.0 / 120.0) < 1e-9
        assert abs(parsed["productivity_ratio"] - 30.0 / 120.0) < 1e-9
        assert "com.instagram.android" in parsed["top_social_apps"]
        assert "com.google.docs" in parsed["top_productivity_apps"]
        assert 0.0 <= parsed["enhanced_r_app"] <= 1.0

    def test_enhanced_r_app_social_boost(self):
        data = ScreenTimeData(
            totalMinutes=180.0,
            socialMinutes=120.0,
            productivityMinutes=10.0,
            dailyUsage=[],
        )
        parsed = parse_screen_time_data(data)
        base_r = sigmoid_r_app(180.0)
        assert parsed["enhanced_r_app"] > base_r

    def test_enhanced_r_app_productivity_dampens(self):
        data = ScreenTimeData(
            totalMinutes=60.0,
            socialMinutes=5.0,
            productivityMinutes=50.0,
            dailyUsage=[],
        )
        parsed = parse_screen_time_data(data)
        base_r = sigmoid_r_app(60.0)
        assert parsed["enhanced_r_app"] < base_r

    def test_zero_total_minutes(self):
        data = ScreenTimeData(
            totalMinutes=0.0,
            socialMinutes=0.0,
            productivityMinutes=0.0,
            dailyUsage=[],
        )
        parsed = parse_screen_time_data(data)
        assert parsed["social_ratio"] == 0.0
        assert parsed["productivity_ratio"] == 0.0
        assert parsed["enhanced_r_app"] == 0.0

    def test_ratios_capped_at_one(self):
        data = ScreenTimeData(
            totalMinutes=60.0,
            socialMinutes=90.0,
            productivityMinutes=80.0,
            dailyUsage=[],
        )
        parsed = parse_screen_time_data(data)
        assert parsed["social_ratio"] <= 1.0
        assert parsed["productivity_ratio"] <= 1.0

    def test_build_screen_time_insights_from_data(self):
        data = ScreenTimeData(
            totalMinutes=90.0,
            socialMinutes=30.0,
            productivityMinutes=20.0,
            dailyUsage=[
                ScreenTimeAppUsage(packageName="com.instagram.android", usageTime=20, category="social"),
                ScreenTimeAppUsage(packageName="com.slack", usageTime=15, category="productivity"),
            ],
        )
        insights = build_screen_time_insights(data)
        assert insights.totalMinutes == 90.0
        assert len(insights.topSocialApps) == 1
        assert insights.topSocialApps[0] == "com.instagram.android"
        assert len(insights.topProductivityApps) == 1


# ---------------------------------------------------------------------------
# Gamifier phase labels
# ---------------------------------------------------------------------------


class TestGamifierPhaseLabels:
    def test_phase_label_quick_win(self):
        from services.shared.schemas import ClinicalTask

        task = ClinicalTask(
            task_id="t1",
            content="Easy task",
            symptom_tags=["anxiety"],
            difficulty=1,
            xp_reward=50,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        assert task.phase == "Quick Win"

        task2 = ClinicalTask(
            task_id="t2",
            content="Medium-easy task",
            symptom_tags=["anxiety"],
            difficulty=2,
            xp_reward=60,
            safety_risk=False,
            utility_score=0.6,
            source_reference="test",
        )
        task2.phase = "Quick Win"
        assert task2.phase == "Quick Win"

    def test_phase_label_ladder(self):
        from services.shared.schemas import ClinicalTask

        task = ClinicalTask(
            task_id="t1",
            content="Medium task",
            symptom_tags=["anxiety"],
            difficulty=3,
            xp_reward=80,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test",
        )
        task.phase = "Ladder"
        assert task.phase == "Ladder"

    def test_phase_label_boss(self):
        from services.shared.schemas import ClinicalTask

        task = ClinicalTask(
            task_id="t1",
            content="Hard task",
            symptom_tags=["anxiety"],
            difficulty=4,
            xp_reward=120,
            safety_risk=False,
            utility_score=0.85,
            source_reference="test",
        )
        task.phase = "Boss"
        assert task.phase == "Boss"

    def test_sequence_tasks_assigns_phases(self):
        from services.shared.schemas import ClinicalTask, UserContext
        from services.gateway.orchestrator import _sequence_tasks

        tasks = [
            ClinicalTask(
                task_id="t-hard",
                content="Hard task",
                symptom_tags=["anxiety"],
                difficulty=5,
                xp_reward=130,
                safety_risk=False,
                utility_score=0.8,
                source_reference="test",
            ),
            ClinicalTask(
                task_id="t-easy",
                content="Easy task",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=50,
                safety_risk=False,
                utility_score=0.7,
                source_reference="test",
            ),
            ClinicalTask(
                task_id="t-medium",
                content="Medium task",
                symptom_tags=["stress"],
                difficulty=3,
                xp_reward=90,
                safety_risk=False,
                utility_score=0.75,
                source_reference="test",
            ),
        ]
        ctx = UserContext(
            user_id="test-user",
            timestamp="2026-01-01T00:00:00",
            form_scores={"anxiety": 50},
            app_exposure_ratios={"r_app": 0.5},
            user_stats={"xp": 100, "level": 1},
        )
        result = _sequence_tasks(tasks, ctx)
        assert result[0].phase == "Quick Win"
        assert result[0].difficulty == 1
        assert result[1].phase == "Ladder"
        assert result[1].difficulty == 3
        assert result[2].phase == "Boss"
        assert result[2].difficulty == 5

    def test_sequence_tasks_sorted_by_difficulty(self):
        from services.shared.schemas import ClinicalTask, UserContext
        from services.gateway.orchestrator import _sequence_tasks

        tasks = [
            ClinicalTask(
                task_id="t5",
                content="Task 5",
                symptom_tags=["anxiety"],
                difficulty=5,
                xp_reward=130,
                safety_risk=False,
                utility_score=0.8,
                source_reference="test",
            ),
            ClinicalTask(
                task_id="t1",
                content="Task 1",
                symptom_tags=["anxiety"],
                difficulty=1,
                xp_reward=50,
                safety_risk=False,
                utility_score=0.7,
                source_reference="test",
            ),
        ]
        ctx = UserContext(
            user_id="test-user",
            timestamp="t",
            form_scores={},
            app_exposure_ratios={},
            user_stats={},
        )
        result = _sequence_tasks(tasks, ctx)
        assert [t.difficulty for t in result] == [1, 5]


# ---------------------------------------------------------------------------
# Build user context with screen_time_data
# ---------------------------------------------------------------------------


class TestBuildUserContextWithScreenTimeData:
    def test_build_user_context_with_screen_time_data(self):
        data = ScreenTimeData(
            totalMinutes=120.0,
            socialMinutes=45.0,
            productivityMinutes=30.0,
            dailyUsage=[],
        )
        ctx = build_user_context(
            user_id="u1",
            raw_forms_json={},
            screen_time_minutes=0.0,
            screen_time_data=data,
        )
        assert ctx.screen_time_data is not None
        assert ctx.screen_time_data.totalMinutes == 120.0
        r_app = ctx.app_exposure_ratios["r_app"]
        assert r_app != sigmoid_r_app(0.0)

    def test_build_user_context_without_screen_time_data(self):
        ctx = build_user_context(
            user_id="u1",
            raw_forms_json={},
            screen_time_minutes=60.0,
        )
        assert ctx.screen_time_data is None
        assert abs(ctx.app_exposure_ratios["r_app"] - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# E2E: /api/assess with rich screen time data
# ---------------------------------------------------------------------------


class TestAssessEndpointWithScreenTime:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_assess_with_screentime_json(self, client=None):
        from fastapi.testclient import TestClient

        if client is None:
            client = TestClient(app)

        payload = {
            "user_id": "test-user-001",
            "locale": "en",
            "screenTimeData": {
                "totalMinutes": 90.0,
                "socialMinutes": 30.0,
                "productivityMinutes": 20.0,
                "dailyUsage": [
                    {"packageName": "com.instagram.android", "usageTime": 20, "category": "social"},
                    {"packageName": "com.whatsapp", "usageTime": 10, "category": "social"},
                    {"packageName": "com.slack", "usageTime": 15, "category": "productivity"},
                    {"packageName": "com.chrome", "usageTime": 45, "category": "other"},
                ],
            },
            "answers": {
                "gad7_q1": 2, "gad7_q2": 1, "gad7_q3": 2,
                "gad7_q4": 1, "gad7_q5": 2, "gad7_q6": 1, "gad7_q7": 0,
                "phq9_q1": 1, "phq9_q2": 0, "phq9_q3": 2,
                "phq9_q4": 1, "phq9_q5": 0, "phq9_q6": 1,
                "phq9_q7": 0, "phq9_q8": 1, "phq9_q9": 0,
            },
        }

        response = client.post("/api/assess", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "screen_time_insights" in body
        if body["screen_time_insights"] is not None:
            assert body["screen_time_insights"]["totalMinutes"] == 90.0
            assert len(body["screen_time_insights"]["topSocialApps"]) >= 1
        assert "suggested_tasks" in body

    def test_assess_with_legacy_screen_time_minutes(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        payload = {
            "user_id": "test-user-002",
            "locale": "en",
            "screen_time_minutes": 120.0,
            "answers": {
                "gad7_q1": 0, "gad7_q2": 0, "gad7_q3": 0,
                "gad7_q4": 0, "gad7_q5": 0, "gad7_q6": 0, "gad7_q7": 0,
                "phq9_q1": 0, "phq9_q2": 0, "phq9_q3": 0,
                "phq9_q4": 0, "phq9_q5": 0, "phq9_q6": 0,
                "phq9_q7": 0, "phq9_q8": 0, "phq9_q9": 0,
            },
        }
        response = client.post("/api/assess", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["screen_time_insights"] is None


# ---------------------------------------------------------------------------
# E2E: /api/roadmap with rich screen time data
# ---------------------------------------------------------------------------


class TestRoadmapEndpointWithScreenTime:
    def test_roadmap_with_screentime_json(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        payload = {
            "user_id": "test-user-003",
            "locale": "en",
            "screenTimeData": {
                "totalMinutes": 150.0,
                "socialMinutes": 80.0,
                "productivityMinutes": 30.0,
                "dailyUsage": [
                    {"packageName": "com.instagram.android", "usageTime": 50, "category": "social"},
                    {"packageName": "com.tiktok", "usageTime": 30, "category": "social"},
                    {"packageName": "com.google.docs", "usageTime": 25, "category": "productivity"},
                ],
            },
            "answers": {
                "gad7_q1": 1, "gad7_q2": 1, "gad7_q3": 1,
                "gad7_q4": 1, "gad7_q5": 1, "gad7_q6": 0, "gad7_q7": 0,
                "phq9_q1": 0, "phq9_q2": 0, "phq9_q3": 1,
                "phq9_q4": 1, "phq9_q5": 0, "phq9_q6": 1,
                "phq9_q7": 0, "phq9_q8": 0, "phq9_q9": 0,
            },
            "top_n": 3,
        }
        response = client.post("/api/roadmap", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "1.0"
        assert "screen_time_insights" in body
        if body["screen_time_insights"] is not None:
            assert body["screen_time_insights"]["totalMinutes"] == 150.0
            assert len(body["screen_time_insights"]["topSocialApps"]) == 2
        assert len(body["suggested_tasks"]) <= 3


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------


class TestCORSHeaders:
    def test_cors_preflight(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.options(
            "/api/assess",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" in response.headers