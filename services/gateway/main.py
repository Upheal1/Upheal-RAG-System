from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.architect.pipeline import run_architect_pipeline
from services.assessment.core import build_user_context
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
    Gateway request contract for assessment input.
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

        candidate_tasks = _kb.retrieve_tasks(user_context, top_k=5)
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

