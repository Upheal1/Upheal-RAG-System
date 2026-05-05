from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.architect.director_override import (
    DirectorDirective,
    apply_directive_constraints,
    load_active_directive,
)
from services.shared.schemas import RetrievalQuery


class TestDirectorDirective:
    """Tests for DirectorDirective dataclass."""

    def test_directive_creation(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            max_difficulty=2,
            xp_multiplier=1.5,
            tag_focus=["anxiety", "depression"],
        )
        assert directive.max_difficulty == 2
        assert directive.xp_multiplier == 1.5
        assert directive.tag_focus == ["anxiety", "depression"]

    def test_default_tag_focus(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
        )
        assert directive.tag_focus == []

    def test_is_expired_no_expiry(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
        )
        assert directive.is_expired() is False

    def test_is_expired_future(self):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            valid_until=future,
        )
        assert directive.is_expired() is False

    def test_is_expired_past(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            valid_until=past,
        )
        assert directive.is_expired() is True


class TestApplyDirectiveConstraints:
    """Tests for apply_directive_constraints function."""

    def test_no_directive_max_difficulty(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
        )
        query = RetrievalQuery(max_difficulty=5)
        result = apply_directive_constraints(directive, query)
        assert result.max_difficulty == 5

    def test_max_difficulty_lowered(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            max_difficulty=2,
        )
        query = RetrievalQuery(max_difficulty=5)
        result = apply_directive_constraints(directive, query)
        assert result.max_difficulty == 2

    def test_max_difficulty_not_increased(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            max_difficulty=4,
        )
        query = RetrievalQuery(max_difficulty=3)
        result = apply_directive_constraints(directive, query)
        assert result.max_difficulty == 3

    def test_tag_focus_added(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            tag_focus=["anxiety", "sleep"],
        )
        query = RetrievalQuery(symptom_keywords=["depression"])
        result = apply_directive_constraints(directive, query)
        assert "anxiety" in result.symptom_keywords
        assert "sleep" in result.symptom_keywords
        assert "depression" in result.symptom_keywords

    def test_tag_focus_deduplicates(self):
        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            tag_focus=["anxiety"],
        )
        query = RetrievalQuery(symptom_keywords=["anxiety", "depression"])
        result = apply_directive_constraints(directive, query)
        assert result.symptom_keywords.count("anxiety") == 1


class TestLoadActiveDirective:
    """Tests for load_active_directive function."""

    @pytest.fixture
    def mock_client(self):
        return MagicMock()

    def test_load_no_directive(self, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        result = load_active_directive(str(uuid4()), supabase_client=mock_client)

        assert result is None

    def test_load_with_active_directive(self, mock_client):
        directive_id = uuid4()
        user_id = uuid4()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "directive_id": str(directive_id),
                "user_id": str(user_id),
                "post_mutation_state": {},
                "retrieval_overrides": {
                    "max_difficulty": 2,
                    "xp_multiplier": 1.5,
                    "tag_focus": ["anxiety"],
                },
                "valid_until": future,
            }
        ]

        result = load_active_directive(str(user_id), supabase_client=mock_client)

        assert result is not None
        assert result.directive_id == directive_id
        assert result.max_difficulty == 2

    def test_load_expired_directive_ignored(self, mock_client):
        directive_id = uuid4()
        user_id = uuid4()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "directive_id": str(directive_id),
                "user_id": str(user_id),
                "post_mutation_state": {},
                "retrieval_overrides": {"max_difficulty": 2},
                "valid_until": past,
            }
        ]

        result = load_active_directive(str(user_id), supabase_client=mock_client)

        assert result is None

    def test_load_invalid_uuid_returns_none(self):
        result = load_active_directive("invalid-uuid")
        assert result is None


class TestPipelineIntegration:
    """Integration tests for director override in pipeline."""

    @patch("services.architect.pipeline.load_active_directive")
    @patch("services.architect.pipeline.retrieve_candidates")
    def test_pipeline_uses_directive(self, mock_retrieve, mock_load_directive):
        from services.architect.pipeline import run_architect_pipeline
        from services.shared.schemas import UserContext

        directive = DirectorDirective(
            directive_id=uuid4(),
            user_id=uuid4(),
            max_difficulty=2,
            tag_focus=["anxiety"],
        )
        mock_load_directive.return_value = directive

        user_ctx = UserContext(
            user_id=str(uuid4()),
            timestamp="2026-05-06T00:00:00Z",
            form_scores={"anxiety": 2},
            app_exposure_ratios={"r_app": 0.5},
            user_stats={"level": 3},
        )

        run_architect_pipeline(
            user_context=user_ctx,
            retrieval_query=RetrievalQuery(max_difficulty=5, symptom_keywords=[]),
        )

        mock_load_directive.assert_called_once()
        call_args = mock_retrieve.call_args
        applied_query = call_args[0][1]
        assert applied_query.max_difficulty == 2
        assert "anxiety" in applied_query.symptom_keywords

    @patch("services.architect.pipeline.load_active_directive")
    @patch("services.architect.pipeline.retrieve_candidates")
    def test_pipeline_skips_expired_directive(self, mock_retrieve, mock_load_directive):
        from services.architect.pipeline import run_architect_pipeline
        from services.shared.schemas import UserContext

        mock_load_directive.return_value = None

        user_ctx = UserContext(
            user_id=str(uuid4()),
            timestamp="2026-05-06T00:00:00Z",
            form_scores={"anxiety": 2},
            app_exposure_ratios={"r_app": 0.5},
            user_stats={"level": 3},
        )

        run_architect_pipeline(
            user_context=user_ctx,
            retrieval_query=RetrievalQuery(max_difficulty=5),
        )

        mock_load_directive.assert_called_once()
        call_args = mock_retrieve.call_args
        applied_query = call_args[0][1]
        assert applied_query.max_difficulty == 5
