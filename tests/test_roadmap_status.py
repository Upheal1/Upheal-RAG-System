"""
Unit tests for roadmap status endpoint (Task 2D).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.gateway.auth_middleware import get_current_user, AuthenticatedUser
from services.gateway.main import app
from services.shared.schemas import ReassessmentStatus


def override_get_current_user():
    return AuthenticatedUser(user_id="test-user-123", email="test@example.com")


app.dependency_overrides[get_current_user] = override_get_current_user


class TestRoadmapStatusEndpoint:
    def test_no_roadmap_returns_assessment_required_true(self) -> None:
        with patch("services.roadmap.router.SupabaseSyncHook") as mock_hook_class:
            mock_hook = MagicMock()
            mock_hook_class.return_value = mock_hook

            mock_result = MagicMock()
            mock_result.data = []
            mock_hook.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

            client = TestClient(app)
            response = client.get("/api/roadmap/test-user-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "test-user-123"
            assert data["assessment_required"] is True
            assert data["roadmap_id"] is None

    def test_active_roadmap_under_90_days(self) -> None:
        with patch("services.roadmap.router.SupabaseSyncHook") as mock_hook_class:
            mock_hook = MagicMock()
            mock_hook_class.return_value = mock_hook

            past_date = (
                datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
            ).isoformat() + "Z"

            mock_result = MagicMock()
            mock_result.data = [
                {
                    "id": "roadmap-123",
                    "status": "ACTIVE",
                    "user_id": "test-user-123",
                    "valid_from": past_date,
                }
            ]
            mock_hook.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

            client = TestClient(app)
            response = client.get("/api/roadmap/test-user-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["assessment_required"] is False
            assert data["roadmap_status"] == "ACTIVE"
            assert data["current_day"] >= 1

    def test_roadmap_over_90_days_requires_assessment(self) -> None:
        with patch("services.roadmap.router.SupabaseSyncHook") as mock_hook_class:
            mock_hook = MagicMock()
            mock_hook_class.return_value = mock_hook

            past_date = (
                datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=100)
            ).isoformat() + "Z"

            mock_result = MagicMock()
            mock_result.data = [
                {
                    "id": "roadmap-123",
                    "status": "ACTIVE",
                    "user_id": "test-user-123",
                    "valid_from": past_date,
                }
            ]
            mock_hook.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

            client = TestClient(app)
            response = client.get("/api/roadmap/test-user-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["current_day"] == 90

    def test_completed_roadmap_requires_assessment(self) -> None:
        with patch("services.roadmap.router.SupabaseSyncHook") as mock_hook_class:
            mock_hook = MagicMock()
            mock_hook_class.return_value = mock_hook

            past_date = (
                datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
            ).isoformat() + "Z"

            mock_result = MagicMock()
            mock_result.data = [
                {
                    "id": "roadmap-123",
                    "status": "COMPLETED",
                    "user_id": "test-user-123",
                    "valid_from": past_date,
                }
            ]
            mock_hook.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

            client = TestClient(app)
            response = client.get("/api/roadmap/test-user-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["assessment_required"] is True
            assert data["roadmap_status"] == "COMPLETED"

    def test_endpoint_requires_auth(self) -> None:
        client = TestClient(app)

        app_dependency_overrides = app.dependency_overrides.copy()
        app.dependency_overrides.pop(get_current_user, None)

        try:
            response = client.get("/api/roadmap/test-user-123/status")
            assert response.status_code == 401
        finally:
            app.dependency_overrides = app_dependency_overrides

    def test_endpoint_health(self) -> None:
        client = TestClient(app)
        response = client.get("/api/roadmap/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
