from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.gateway.orchestrator import run_assessment_chain
from services.shared.logging import get_logger
from services.shared.schemas import AssessGatewayResponse
from services.assessment.router import router as assessment_router
from services.knowledge_base.router import router as kb_router
from services.architect.router import router as architect_router
from services.ingestion.router import router as ingestion_router
from services.auditor.router import router as auditor_router


logger = get_logger(__name__)

app = FastAPI(
    title="Upheal Microservices Gateway",
    version="0.1.0",
    description="In-process microservices scaffolding (gateway orchestrates domain modules).",
)


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
    """

    user_id: str
    session_id: Optional[str] = None
    locale: str = "en"
    raw_forms_json: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        default_factory=dict
    )
    screen_time_minutes: float = 0.0
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
def assess(payload: Dict[str, Any]) -> AssessGatewayResponse:
    try:
        req = AssessRequest.model_validate(payload)
        raw_payload: Any = req.raw_forms_json
        if req.answers is not None:
            if isinstance(raw_payload, dict):
                raw_payload = {**raw_payload, "answers": req.answers}
            else:
                raw_payload = {"answers": req.answers}

        return run_assessment_chain(
            user_id=req.user_id,
            raw_payload=raw_payload,
            screen_time_minutes=req.screen_time_minutes,
            locale=req.locale,
            session_id=req.session_id,
            answers=req.answers,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Assessment failed")
        raise HTTPException(status_code=500, detail=f"Assessment failed: {e}")


# Domain routers (primarily for /health endpoints).
app.include_router(assessment_router, prefix="/assessment", tags=["assessment"])
app.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
app.include_router(kb_router, prefix="/knowledge_base", tags=["knowledge_base"])
app.include_router(architect_router, prefix="/architect", tags=["architect"])
app.include_router(auditor_router, prefix="/auditor", tags=["auditor"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
