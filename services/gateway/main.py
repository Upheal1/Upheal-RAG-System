from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.gateway.auth_middleware import AuthenticatedUser, get_current_user

from services.gateway.orchestrator import run_assessment_chain
from services.gateway.schemas import RoadmapRequest, RoadmapResponse
from services.shared.logging import get_logger
from services.shared.schemas import (
    AssessGatewayResponse,
    ScreenTimeData,
    ScreenTimeInsights,
)
from services.assessment.router import router as assessment_router
from services.knowledge_base.router import router as kb_router
from services.architect.router import router as architect_router
from services.ingestion.router import router as ingestion_router
from services.auditor.router import router as auditor_router
from services.telemetry.router import router as telemetry_router
from services.roadmap.router import router as roadmap_router


logger = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Upheal Microservices Gateway",
    version="0.1.0",
    description="In-process microservices scaffolding (gateway orchestrates domain modules).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter


class AssessRequest(BaseModel):
    """
    Gateway request for `POST /api/assess`.

    - `user_id` (required): stable identifier for the caller.
    - `raw_forms_json`: optional wrapper dict or list. Prefer
      `{"answers": {"gad7_q1": 0..3, ...}, "risk_flags": {"suicidal": false}}`.
      A flat dict whose keys look like GAD/PHQ question ids is treated as answers.
    - `answers`: optional; merged into `raw_forms_json` as `answers` when provided
      (supports legacy clients that send top-level `answers` only).
    - `screen_time_minutes`: drives sigmoid R_app in `UserContext.app_exposure_ratios`.
    - `screenTimeData`: rich per-app screen time from Flutter. When provided,
      `screen_time_minutes` is derived from `totalMinutes` and the parser computes
      `social_ratio` / `productivity_ratio` for enhanced `r_app`.
    """

    user_id: str
    session_id: Optional[str] = None
    locale: str = "en"
    raw_forms_json: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        default_factory=dict
    )
    screen_time_minutes: float = 0.0
    screenTimeData: Optional[ScreenTimeData] = None
    answers: Optional[Dict[str, int]] = None


class HealthResponse(BaseModel):
    status: str
    knowledge_base_healthy: bool
    knowledge_base_documents: int


# Pydantic v2 on newer Python versions can require an explicit rebuild for
# runtime validation in FastAPI dependency solving.
try:  # pragma: no cover
    AssessRequest.model_rebuild()
    AssessGatewayResponse.model_rebuild()
    RoadmapRequest.model_rebuild()
    RoadmapResponse.model_rebuild()
except Exception:
    pass


@app.get("/health", response_model=HealthResponse, tags=["gateway"])
def health_check() -> HealthResponse:
    from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

    _kb = ChromaKnowledgeBase()
    return HealthResponse(
        status="ok",
        knowledge_base_healthy=_kb.is_healthy(),
        knowledge_base_documents=_kb.get_document_count(),
    )


@app.post("/api/assess", response_model=AssessGatewayResponse, tags=["assessment"])
@limiter.limit("10/minute")
def assess(
    payload: Dict[str, Any],
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AssessGatewayResponse:
    try:
        req = AssessRequest.model_validate(payload)
        raw_payload: Any = req.raw_forms_json
        if req.answers is not None:
            if isinstance(raw_payload, dict):
                raw_payload = {**raw_payload, "answers": req.answers}
            else:
                raw_payload = {"answers": req.answers}

        effective_screen_time = req.screen_time_minutes
        if req.screenTimeData is not None and req.screenTimeData.totalMinutes > 0:
            effective_screen_time = req.screenTimeData.totalMinutes

        return run_assessment_chain(
            user_id=user.user_id,
            raw_payload=raw_payload,
            screen_time_minutes=effective_screen_time,
            locale=req.locale,
            session_id=req.session_id,
            answers=req.answers,
            screen_time_data=req.screenTimeData,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Assessment failed")
        raise HTTPException(status_code=500, detail=f"Assessment failed: {e}")


@app.post("/api/roadmap", response_model=RoadmapResponse, tags=["roadmap"])
def generate_roadmap(
    payload: Dict[str, Any],
    user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapResponse:
    """
    Generate a personalized clinical roadmap.

    Returns a clean `FinalRoadmap` response without legacy clinical fields.
    This is the modern API contract for new clients.
    """
    try:
        req = RoadmapRequest.model_validate(payload)
        raw_payload: Any = req.raw_forms_json
        if req.answers is not None:
            if isinstance(raw_payload, dict):
                raw_payload = {**raw_payload, "answers": req.answers}
            else:
                raw_payload = {"answers": req.answers}

        effective_screen_time = req.screen_time_minutes
        if req.screenTimeData is not None and req.screenTimeData.totalMinutes > 0:
            effective_screen_time = req.screenTimeData.totalMinutes

        chain_response = run_assessment_chain(
            user_id=user.user_id,
            raw_payload=raw_payload,
            screen_time_minutes=effective_screen_time,
            locale=req.locale,
            session_id=req.session_id,
            answers=req.answers,
            top_n=req.top_n,
            screen_time_data=req.screenTimeData,
        )

        road_screen_insights = None
        if chain_response.screen_time_insights is not None:
            road_screen_insights = chain_response.screen_time_insights

        roadmap = RoadmapResponse(
            user_id=chain_response.user_id,
            overview_paragraph=chain_response.overview_paragraph,
            suggested_tasks=chain_response.suggested_tasks[: req.top_n],
            safety_status=chain_response.safety_status,
            next_checkup_days=chain_response.next_checkup_days,
            generated_at=chain_response.timestamp,
            session_id=chain_response.session_id,
            screen_time_insights=road_screen_insights,
        )
        return roadmap
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Roadmap generation failed")
        raise HTTPException(status_code=500, detail=f"Roadmap generation failed: {e}")


# Domain routers (primarily for /health endpoints).
app.include_router(assessment_router, prefix="/assessment", tags=["assessment"])
app.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
app.include_router(kb_router, prefix="/knowledge_base", tags=["knowledge_base"])
app.include_router(architect_router, prefix="/architect", tags=["architect"])
app.include_router(auditor_router, prefix="/auditor", tags=["auditor"])
app.include_router(telemetry_router, prefix="/api", tags=["telemetry"])
app.include_router(roadmap_router, prefix="/api/roadmap", tags=["roadmap"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
