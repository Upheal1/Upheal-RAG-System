from __future__ import annotations

from typing import Any, Dict, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.architect.pipeline import run_architect_pipeline
from services.assessment.core import build_retrieval_query_text, build_user_context, infer_answers_dict
from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase
from services.shared.logging import get_logger
from services.shared.schemas import FinalRoadmap
from services.assessment.router import router as assessment_router
from services.knowledge_base.router import router as kb_router
from services.architect.router import router as architect_router
from services.ingestion.router import router as ingestion_router


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
    raw_forms_json: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(default_factory=dict)
    screen_time_minutes: float = 0.0
    answers: Optional[Dict[str, int]] = None


class HealthResponse(BaseModel):
    status: str
    knowledge_base_healthy: bool
    knowledge_base_documents: int


_kb = ChromaKnowledgeBase()


@app.get("/health", response_model=HealthResponse, tags=["gateway"])
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        knowledge_base_healthy=_kb.is_healthy(),
        knowledge_base_documents=_kb.get_document_count(),
    )


@app.post("/api/assess", response_model=FinalRoadmap, tags=["assessment"])
def assess(req: AssessRequest) -> FinalRoadmap:
    try:
        raw_payload: Any = req.raw_forms_json
        if req.answers is not None:
            if isinstance(raw_payload, dict):
                raw_payload = {**raw_payload, "answers": req.answers}
            else:
                # If the payload is a list, wrap answers for inference.
                raw_payload = {"answers": req.answers}

        user_context = build_user_context(
            user_id=req.user_id,
            raw_forms_json=raw_payload,
            screen_time_minutes=req.screen_time_minutes,
        )

        answers_for_query = infer_answers_dict(raw_payload) or {}
        query_text = build_retrieval_query_text(user_context, answers_for_query)

        candidate_tasks = _kb.retrieve_tasks(
            user_context, query_text=query_text, top_k=5
        )
        roadmap = run_architect_pipeline(user_context, candidate_tasks, top_n=5)
        return roadmap
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

