from fastapi import APIRouter, HTTPException, status

from services.shared.logging import get_logger
from services.telemetry.schemas import TelemetryRequest, TelemetryResponse
from services.telemetry.service import create_telemetry_service

logger = get_logger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post(
    "/",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        204: {"description": "Idempotent duplicate (already logged)"},
    },
)
def log_telemetry(request: TelemetryRequest) -> TelemetryResponse:
    """
    Log a user-task interaction event.

    Enums:
        - interaction_type: VIEWED | STARTED | COMPLETED | SKIPPED

    Returns:
        201: Created log with log_id and recorded_at
        204: Idempotent - already logged (dedupe_key match)
        500: Server error
    """
    try:
        service = create_telemetry_service()
        return service.log_interaction(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("telemetry.endpoint.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log telemetry: {e}",
        )
