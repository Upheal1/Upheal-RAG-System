"""
Unit tests for the POST /api/roadmap endpoint (A-YAH-10).

Covers:
- Happy path returns 200 with tasks array and overview
- Crisis path returns RED safety_status
- Contract snapshot test prevents accidental field removal
- Locale propagation (EN/AR)
- top_n parameter limits task count
- Empty answers → valid roadmap with defaults
- Response contains NO legacy fields
"""

from __future__ import annotations

from typing import List
from unittest.mock import patch

from services.gateway.auth_middleware import get_current_user, AuthenticatedUser
from services.gateway.main import app
from services.gateway.schemas import RoadmapRequest, RoadmapResponse
from services.shared.schemas import ClinicalTask


def override_get_current_user():
    return AuthenticatedUser(user_id="test-user-001", email="test@example.com")


app.dependency_overrides[get_current_user] = override_get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_tasks() -> List[ClinicalTask]:
    return [
        ClinicalTask(
            task_id=f"t-{i}",
            content=f"Task {i}: therapeutic activity.",
            symptom_tags=["anxiety", "stress"],
            difficulty=i % 3 + 1,
            xp_reward=50 + i * 10,
            safety_risk=False,
            utility_score=0.7,
            source_reference="test-ref",
            metadata={"similarity": 0.8},
        )
        for i in range(5)
    ]


# ===================================================================
# 1. Schema validation
# ===================================================================


class TestRoadmapRequestSchema:
    def test_minimal_request(self):
        req = RoadmapRequest(user_id="u1")
        assert req.user_id == "u1"
        assert req.locale == "en"
        assert req.top_n == 5

    def test_top_n_range(self):
        req = RoadmapRequest(user_id="u", top_n=10)
        assert req.top_n == 10

    def test_answers_merging(self):
        answers = {f"gad7_q{i}": 2 for i in range(1, 8)}
        req = RoadmapRequest(
            user_id="u",
            raw_forms_json={"answers": answers},
            answers=answers,
        )
        assert req.answers == answers


class TestRoadmapResponseSchema:
    def test_minimal_response(self):
        resp = RoadmapResponse(
            user_id="u",
            overview_paragraph="test",
            safety_status="GREEN",
            next_checkup_days=14,
            generated_at="2024-01-01T00:00:00Z",
        )
        assert resp.user_id == "u"
        assert resp.version == "1.0"
        assert resp.session_id is None

    def test_has_no_legacy_fields(self):
        """RoadmapResponse should NOT have anxiety_probability, etc."""
        fields = set(RoadmapResponse.model_fields.keys())
        assert "anxiety_probability" not in fields
        assert "depression_probability" not in fields
        assert "severity" not in fields
        assert "comorbidity" not in fields
        assert "rag_recommendations" not in fields


# ===================================================================
# 2. Happy path
# ===================================================================


class TestRoadmapHappyPath:
    @patch("services.gateway.main.run_assessment_chain")
    def test_returns_200_with_tasks_and_overview(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        tasks = _sample_tasks()
        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "test-user",
                "overview_paragraph": "Here are your next steps.",
                "suggested_tasks": tasks,
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "2024-01-01T00:00:00Z",
                "session_id": "s-1",
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post(
            "/api/roadmap",
            json={
                "user_id": "test-user",
                "session_id": "s-1",
                "screen_time_minutes": 90,
                "answers": {f"gad7_q{i}": 1 for i in range(1, 8)},
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test-user"
        assert data["overview_paragraph"] == "Here are your next steps."
        assert len(data["suggested_tasks"]) == 5
        assert data["safety_status"] == "GREEN"
        assert data["next_checkup_days"] == 14

    @patch("services.gateway.main.run_assessment_chain")
    def test_response_has_generated_at(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": [],
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "2024-06-15T12:00:00Z",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post("/api/roadmap", json={"user_id": "u"})

        assert resp.status_code == 200
        assert resp.json()["generated_at"] == "2024-06-15T12:00:00Z"

    @patch("services.gateway.main.run_assessment_chain")
    def test_response_has_version_field(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": [],
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post("/api/roadmap", json={"user_id": "u"})

        assert resp.status_code == 200
        assert resp.json()["version"] == "1.0"


# ===================================================================
# 3. Crisis path (RED)
# ===================================================================


class TestRoadmapCrisisPath:
    @patch("services.gateway.main.run_assessment_chain")
    def test_crisis_text_returns_red_status(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "I'm really sorry you're going through this...",
                "suggested_tasks": [
                    ClinicalTask(
                        task_id="emergency_resources",
                        content="Contact a crisis helpline.",
                        symptom_tags=["suicidal"],
                        difficulty=5,
                        xp_reward=0,
                        safety_risk=False,
                        utility_score=0.0,
                        source_reference="auditor",
                        metadata={},
                    )
                ],
                "safety_status": "RED",
                "next_checkup_days": 1,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post(
            "/api/roadmap",
            json={"user_id": "u", "locale": "en"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_status"] == "RED"
        assert data["next_checkup_days"] == 1
        assert len(data["suggested_tasks"]) == 1
        assert data["suggested_tasks"][0]["task_id"] == "emergency_resources"


# ===================================================================
# 4. Contract snapshot test
# ===================================================================


class TestRoadmapContractSnapshot:
    @patch("services.gateway.main.run_assessment_chain")
    def test_exact_field_set(self, mock_chain):
        """
        Validates the exact JSON fields returned by POST /api/roadmap.
        Prevents accidental field addition or removal.
        """
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test overview",
                "suggested_tasks": [],
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "2024-01-01T00:00:00Z",
                "session_id": "s-1",
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post(
            "/api/roadmap",
            json={"user_id": "u", "session_id": "s-1"},
        )

        assert resp.status_code == 200
        fields = set(resp.json().keys())

        expected = {
            "user_id",
            "overview_paragraph",
            "suggested_tasks",
            "safety_status",
            "next_checkup_days",
            "generated_at",
            "session_id",
            "version",
            "screen_time_insights",
        }
        assert fields == expected, (
            f"Contract changed! Extra: {fields - expected}, Missing: {expected - fields}"
        )

    @patch("services.gateway.main.run_assessment_chain")
    def test_no_legacy_fields_in_response(self, mock_chain):
        """Confirms the roadmap response does NOT leak legacy clinical fields."""
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": [],
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post("/api/roadmap", json={"user_id": "u"})

        data = resp.json()
        legacy_fields = {
            "anxiety_probability",
            "depression_probability",
            "severity",
            "comorbidity",
            "rag_recommendations",
            "query_used",
        }
        for field in legacy_fields:
            assert field not in data, (
                f"Legacy field '{field}' leaked into roadmap response"
            )


# ===================================================================
# 5. Locale propagation
# ===================================================================


class TestRoadmapLocale:
    @patch("services.gateway.main.run_assessment_chain")
    def test_english_locale(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": [],
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        client.post("/api/roadmap", json={"user_id": "u", "locale": "en"})

        mock_chain.assert_called_once()
        call_kwargs = mock_chain.call_args[1]
        assert call_kwargs["locale"] == "en"

    @patch("services.gateway.main.run_assessment_chain")
    def test_arabic_locale(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": [],
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        client.post("/api/roadmap", json={"user_id": "u", "locale": "ar"})

        mock_chain.assert_called_once()
        call_kwargs = mock_chain.call_args[1]
        assert call_kwargs["locale"] == "ar"


# ===================================================================
# 6. top_n parameter
# ===================================================================


class TestRoadmapTopN:
    @patch("services.gateway.main.run_assessment_chain")
    def test_top_n_limits_task_count(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        tasks = _sample_tasks()
        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": tasks,
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post(
            "/api/roadmap",
            json={"user_id": "u", "top_n": 3},
        )

        assert resp.status_code == 200
        assert len(resp.json()["suggested_tasks"]) == 3

    @patch("services.gateway.main.run_assessment_chain")
    def test_top_n_one_task(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        tasks = _sample_tasks()
        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "test",
                "suggested_tasks": tasks,
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post(
            "/api/roadmap",
            json={"user_id": "u", "top_n": 1},
        )

        assert resp.status_code == 200
        assert len(resp.json()["suggested_tasks"]) == 1


# ===================================================================
# 7. Empty answers → defaults
# ===================================================================


class TestRoadmapEmptyAnswers:
    @patch("services.gateway.main.run_assessment_chain")
    def test_no_answers_returns_valid_roadmap(self, mock_chain):
        from services.gateway.main import app
        from fastapi.testclient import TestClient

        mock_chain.return_value = type(
            "MockResponse",
            (),
            {
                "user_id": "u",
                "overview_paragraph": "Here are personalized next steps.",
                "suggested_tasks": _sample_tasks(),
                "safety_status": "GREEN",
                "next_checkup_days": 14,
                "timestamp": "t",
                "session_id": None,
                "screen_time_insights": None,
            },
        )()

        client = TestClient(app)
        resp = client.post(
            "/api/roadmap",
            json={"user_id": "u"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["overview_paragraph"] != ""
        assert data["safety_status"] in ("GREEN", "YELLOW", "RED")
