from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, cast

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.architect.pipeline import run_architect_pipeline
from services.assessment.core import (
    build_retrieval_query_text,
    build_user_context,
    gad7_raw_total,
    infer_answers_dict,
    phq9_raw_total,
    severity_label_from_gad7_total,
    severity_label_from_phq9_total,
    sigmoid_probability_from_scale_total,
)
from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase
from services.shared.logging import get_logger
from services.shared.schemas import (
    AssessGatewayResponse,
    FinalRoadmap,
    LegacyRAGRecommendation,
    RetrievalQuery,
)
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


_kb = ChromaKnowledgeBase()

# Pydantic v2 on newer Python versions can require an explicit rebuild for
# runtime validation in FastAPI dependency solving.
try:  # pragma: no cover
    AssessRequest.model_rebuild()
    AssessGatewayResponse.model_rebuild()
except Exception:
    pass


@app.get("/health", response_model=HealthResponse, tags=["gateway"])
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        knowledge_base_healthy=_kb.is_healthy(),
        knowledge_base_documents=_kb.get_document_count(),
    )


@app.post("/api/assess", response_model=AssessGatewayResponse, tags=["assessment"])
def assess(payload: Dict[str, Any]) -> AssessGatewayResponse:
    try:
        # Workaround for Python 3.14 + FastAPI/Pydantic TypeAdapter "not fully defined":
        # validate manually instead of relying on FastAPI's body parsing adapter.
        req = AssessRequest.model_validate(payload)
        raw_payload: Any = req.raw_forms_json
        if req.answers is not None:
            if isinstance(raw_payload, dict):
                raw_payload = {**raw_payload, "answers": req.answers}
            else:
                # If the payload is a list, wrap answers for inference.
                raw_payload = {"answers": req.answers}

        def translate_to_legacy(
            *,
            roadmap: FinalRoadmap,
            answers: Dict[str, int],
            query_used: str,
            session_id: Optional[str],
            form_scores: Dict[str, int],
            r_app: float,
        ) -> AssessGatewayResponse:
            rag_recommendations = [
                LegacyRAGRecommendation(
                    source=str(t.source_reference),
                    section=str(t.metadata.get("section") or ""),
                    content=str(t.content),
                    similarity=float(t.metadata.get("similarity", 0.0) or 0.0),
                    pages=str(t.metadata.get("pages") or ""),
                )
                for t in (roadmap.suggested_tasks or [])
            ]

            if answers:
                gad_total = gad7_raw_total(answers)
                phq_total = phq9_raw_total(answers)
                anxiety_probability = sigmoid_probability_from_scale_total(
                    gad_total, 21, k=0.05
                )
                depression_probability = sigmoid_probability_from_scale_total(
                    phq_total, 27, k=0.05
                )
                severity = {
                    "anxiety": severity_label_from_gad7_total(gad_total),
                    "depression": severity_label_from_phq9_total(phq_total),
                }
                comorbidity = (
                    "true"
                    if (anxiety_probability > 0.5 and depression_probability > 0.5)
                    else "false"
                )
            else:
                gad_total = 0
                phq_total = 0
                anxiety_probability = 0.0
                depression_probability = 0.0
                severity = {"anxiety": "Mild", "depression": "Mild"}
                comorbidity = "false"

            # Always log a compact breakdown for debugging and manual QA.
            logger.info(
                "Score breakdown user_id=%s session_id=%s gad7_total=%s phq9_total=%s anxiety_p=%.4f depression_p=%.4f severity=%s form_scores=%s r_app=%.4f",
                req.user_id,
                session_id,
                gad_total,
                phq_total,
                float(anxiety_probability),
                float(depression_probability),
                severity,
                form_scores,
                float(r_app),
            )

            return AssessGatewayResponse(
                **roadmap.model_dump(),
                anxiety_probability=float(anxiety_probability),
                depression_probability=float(depression_probability),
                severity=severity,
                comorbidity=comorbidity,
                rag_recommendations=rag_recommendations,
                query_used=str(query_used),
                timestamp=datetime.now(timezone.utc).isoformat(),
                session_id=session_id,
            )

        user_context = build_user_context(
            user_id=req.user_id,
            raw_forms_json=raw_payload,
            screen_time_minutes=req.screen_time_minutes,
        )

        answers_for_query = infer_answers_dict(raw_payload) or {}
        query_text = build_retrieval_query_text(user_context, answers_for_query)

        candidate_tasks = _kb.retrieve_tasks(
            RetrievalQuery(query_text=query_text),
            user_context,
            top_k=5,
        )
        roadmap = run_architect_pipeline(
            user_context, candidate_tasks, top_n=5, locale=req.locale
        )

        # Return combined roadmap + legacy fields for Flutter compatibility.
        return translate_to_legacy(
            roadmap=roadmap,
            answers=answers_for_query,
            query_used=query_text,
            session_id=req.session_id,
            form_scores=dict(user_context.form_scores),
            r_app=float(user_context.app_exposure_ratios.get("r_app", 0.0)),
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
