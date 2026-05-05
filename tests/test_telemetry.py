from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from services.telemetry.schemas import (
    InteractionType,
    TelemetryRequest,
    TelemetryResponse,
)
from services.telemetry.service import TelemetryService


class TestTelemetryRequest:
    """Tests for TelemetryRequest schema validation."""

    def test_valid_request_all_fields(self):
        user_id = uuid4()
        task_id = uuid4()
        request = TelemetryRequest(
            user_id=user_id,
            task_id=task_id,
            interaction_type=InteractionType.VIEWED,
            completion_time=30,
            drop_off_point=0.5,
            xp_earned=10,
        )
        assert request.user_id == user_id
        assert request.task_id == task_id
        assert request.interaction_type == InteractionType.VIEWED

    def test_valid_request_minimal_fields(self):
        user_id = uuid4()
        task_id = uuid4()
        request = TelemetryRequest(
            user_id=user_id,
            task_id=task_id,
            interaction_type=InteractionType.COMPLETED,
        )
        assert request.completion_time is None
        assert request.drop_off_point is None
        assert request.xp_earned == 0

    @pytest.mark.parametrize("interaction_type", list(InteractionType))
    def test_all_interaction_types_valid(self, interaction_type: InteractionType):
        request = TelemetryRequest(
            user_id=uuid4(),
            task_id=uuid4(),
            interaction_type=interaction_type,
        )
        assert request.interaction_type == interaction_type

    def test_invalid_interaction_type(self):
        with pytest.raises(ValidationError):
            TelemetryRequest(
                user_id=uuid4(),
                task_id=uuid4(),
                interaction_type="INVALID",
            )

    def test_invalid_completion_time_negative(self):
        with pytest.raises(ValidationError):
            TelemetryRequest(
                user_id=uuid4(),
                task_id=uuid4(),
                interaction_type=InteractionType.VIEWED,
                completion_time=-1,
            )

    def test_invalid_drop_off_point_above_1(self):
        with pytest.raises(ValidationError):
            TelemetryRequest(
                user_id=uuid4(),
                task_id=uuid4(),
                interaction_type=InteractionType.VIEWED,
                drop_off_point=1.5,
            )

    def test_invalid_drop_off_point_below_0(self):
        with pytest.raises(ValidationError):
            TelemetryRequest(
                user_id=uuid4(),
                task_id=uuid4(),
                interaction_type=InteractionType.VIEWED,
                drop_off_point=-0.1,
            )

    def test_invalid_xp_negative(self):
        with pytest.raises(ValidationError):
            TelemetryRequest(
                user_id=uuid4(),
                task_id=uuid4(),
                interaction_type=InteractionType.VIEWED,
                xp_earned=-5,
            )


class TestTelemetryService:
    """Tests for TelemetryService business logic."""

    @pytest.fixture
    def mock_sync_hook(self):
        hook = MagicMock()
        hook.insert_row.return_value = {
            "log_id": str(uuid4()),
            "user_id": str(uuid4()),
            "task_id": str(uuid4()),
            "interaction_type": "COMPLETED",
            "recorded_at": "2026-05-06T01:00:00Z",
        }
        return hook

    @pytest.fixture
    def service(self, mock_sync_hook):
        return TelemetryService(sync_hook=mock_sync_hook)

    def test_log_interaction_success(self, service, mock_sync_hook):
        user_id = uuid4()
        task_id = uuid4()
        request = TelemetryRequest(
            user_id=user_id,
            task_id=task_id,
            interaction_type=InteractionType.COMPLETED,
            completion_time=60,
            xp_earned=15,
        )

        response = service.log_interaction(request)

        assert response.user_id == user_id
        assert response.task_id == task_id
        assert response.interaction_type == InteractionType.COMPLETED
        assert response.idempotent is False
        mock_sync_hook.insert_row.assert_called_once()

    def test_log_interaction_idempotent_hit(self, service):
        dedupe_key = uuid4()
        existing_log_id = uuid4()
        user_id = uuid4()
        task_id = uuid4()
        existing_record = {
            "log_id": str(existing_log_id),
            "user_id": str(user_id),
            "task_id": str(task_id),
            "interaction_type": "VIEWED",
            "recorded_at": "2026-05-06T01:00:00Z",
        }

        def fetch_one_side_effect(filters):
            return existing_record

        service.sync.fetch_one = fetch_one_side_effect

        request = TelemetryRequest(
            user_id=user_id,
            task_id=task_id,
            interaction_type=InteractionType.VIEWED,
            dedupe_key=dedupe_key,
        )

        response = service.log_interaction(request)

        assert response.idempotent is True

    def test_log_interaction_new_dedupe_key(self, service, mock_sync_hook):
        dedupe_key = uuid4()
        new_log_id = uuid4()
        user_id = uuid4()
        task_id = uuid4()

        mock_sync_hook.insert_row.return_value = {
            "log_id": str(new_log_id),
            "user_id": str(user_id),
            "task_id": str(task_id),
            "interaction_type": "STARTED",
            "recorded_at": "2026-05-06T01:00:00Z",
        }

        def fetch_one_side_effect(filters):
            return None

        mock_sync_hook.fetch_one = fetch_one_side_effect

        request = TelemetryRequest(
            user_id=user_id,
            task_id=task_id,
            interaction_type=InteractionType.STARTED,
            dedupe_key=dedupe_key,
        )

        response = service.log_interaction(request)

        assert response.idempotent is False
        call_args = mock_sync_hook.insert_row.call_args[0][0]
        assert call_args.get("log_id") == str(dedupe_key)


class TestTelemetryResponse:
    """Tests for TelemetryResponse schema."""

    def test_response_creation(self):
        log_id = uuid4()
        user_id = uuid4()
        task_id = uuid4()

        response = TelemetryResponse(
            log_id=log_id,
            user_id=user_id,
            task_id=task_id,
            interaction_type=InteractionType.SKIPPED,
            recorded_at="2026-05-06T01:00:00Z",
            idempotent=False,
        )

        assert response.log_id == log_id
        assert response.idempotent is False
