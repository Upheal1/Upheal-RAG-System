from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from services.shared.logging import get_logger
from services.shared.state import SupabaseSyncHook

from services.telemetry.schemas import (
    InteractionType,
    TelemetryRequest,
    TelemetryResponse,
)

log = get_logger(__name__)

_TABLE_NAME = "interaction_logs"


class TelemetryService:
    """
    Service for logging user-task interactions to Supabase.

    Uses optimistic locking via SupabaseSyncHook for concurrent safety.
    """

    def __init__(self, sync_hook: Optional[SupabaseSyncHook] = None):
        self._sync = sync_hook

    @property
    def sync(self) -> SupabaseSyncHook:
        if self._sync is None:
            self._sync = SupabaseSyncHook(_TABLE_NAME)
        return self._sync

    def log_interaction(
        self,
        request: TelemetryRequest,
    ) -> TelemetryResponse:
        """
        Log a user-task interaction to the database.

        If dedupe_key is provided, checks for existing log with same key
        and returns existing record (idempotent behavior).

        Parameters
        ----------
        request : TelemetryRequest
            Validated telemetry request.

        Returns
        -------
        TelemetryResponse
            Created log with server timestamp.
        """
        if request.dedupe_key:
            existing = self._check_existing_dedupe(request.dedupe_key)
            if existing:
                log.info(
                    "telemetry.idempotent_hit",
                    dedupe_key=str(request.dedupe_key),
                    log_id=existing["log_id"],
                )
                return TelemetryResponse(
                    log_id=UUID(existing["log_id"]),
                    user_id=UUID(existing["user_id"]),
                    task_id=UUID(existing["task_id"]),
                    interaction_type=InteractionType(existing["interaction_type"]),
                    recorded_at=existing["recorded_at"],
                    idempotent=True,
                )

        row = {
            "user_id": str(request.user_id),
            "task_id": str(request.task_id),
            "interaction_type": request.interaction_type.value,
            "completion_time": request.completion_time,
            "drop_off_point": request.drop_off_point,
            "xp_earned": request.xp_earned,
        }

        if request.dedupe_key:
            row["log_id"] = str(request.dedupe_key)

        result = self.sync.insert_row(row)

        log.info(
            "telemetry.logged",
            user_id=str(request.user_id),
            task_id=str(request.task_id),
            interaction_type=request.interaction_type.value,
            log_id=result.get("log_id", "unknown"),
        )

        return TelemetryResponse(
            log_id=UUID(result["log_id"]),
            user_id=request.user_id,
            task_id=request.task_id,
            interaction_type=request.interaction_type,
            recorded_at=result["recorded_at"],
            idempotent=False,
        )

    def _check_existing_dedupe(self, dedupe_key: UUID) -> Optional[dict]:
        """Check if a log with the given dedupe_key already exists."""
        try:
            return self.sync.fetch_one({"log_id": str(dedupe_key)})
        except Exception:
            return None


def create_telemetry_service() -> TelemetryService:
    """Factory function to create TelemetryService with default config."""
    return TelemetryService()
