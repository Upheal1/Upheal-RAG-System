"""
Gateway orchestrator — wires Profiler → Architect → Auditor into a single
assessment chain with per-stage logging, timing, and safe error handling.

The Gamifier (A-YAH-06) slot is reserved as a no-op hook for later insertion.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    UserContext,
)

logger = get_logger(__name__)
_kb = ChromaKnowledgeBase()

ASSESSMENT_STAGE = "gateway.assess"


# ---------------------------------------------------------------------------
# Gamifier hook (no-op placeholder — A-YAH-06)
# ---------------------------------------------------------------------------


def _sequence_tasks(
    tasks: list,
    user_context: UserContext,
) -> list:
    """
    Hook for A-YAH-06 Gamifier Agent.

    When the Gamifier is implemented, this should apply XP scaling
    and Quick Win → Ladder → Boss sequencing.

    Currently returns tasks unchanged (pass-through).
    """
    return tasks


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


def _run_profiler(
    user_id: str,
    raw_payload: Any,
    screen_time_minutes: float,
) -> UserContext:
    t0 = time.monotonic()
    logger.info(f"{ASSESSMENT_STAGE}.profiler.start", user_id=user_id)

    ctx = build_user_context(
        user_id=user_id,
        raw_forms_json=raw_payload,
        screen_time_minutes=screen_time_minutes,
    )

    elapsed = time.monotonic() - t0
    logger.info(
        f"{ASSESSMENT_STAGE}.profiler.done",
        user_id=user_id,
        form_scores=ctx.form_scores,
        r_app=ctx.app_exposure_ratios.get("r_app", 0.0),
        duration_ms=round(elapsed * 1000, 2),
    )
    return ctx


def _run_architect(
    user_context: UserContext,
    query_text: str,
    locale: str,
    top_n: int = 5,
) -> FinalRoadmap:
    t0 = time.monotonic()
    logger.info(
        f"{ASSESSMENT_STAGE}.architect.start",
        user_id=user_context.user_id,
        query_text=query_text,
        locale=locale,
    )

    candidate_tasks = _kb.retrieve_tasks(
        RetrievalQuery(query_text=query_text),
        user_context,
        top_k=top_n,
    )

    candidate_tasks = _sequence_tasks(list(candidate_tasks), user_context)

    roadmap = run_architect_pipeline(
        user_context,
        candidate_tasks,
        top_n=top_n,
        locale=locale,
    )

    elapsed = time.monotonic() - t0
    logger.info(
        f"{ASSESSMENT_STAGE}.architect.done",
        user_id=user_context.user_id,
        task_count=len(roadmap.suggested_tasks),
        safety_status=roadmap.safety_status,
        duration_ms=round(elapsed * 1000, 2),
    )
    return roadmap


def _assemble_response(
    roadmap: FinalRoadmap,
    user_context: UserContext,
    answers: Dict[str, int],
    query_used: str,
    session_id: Optional[str],
) -> AssessGatewayResponse:
    t0 = time.monotonic()
    logger.info(f"{ASSESSMENT_STAGE}.assemble.start", user_id=user_context.user_id)

    rag_recommendations = [
        LegacyRAGRecommendation(
            source=str(t.source_reference),
            section=str(t.metadata.get("section") or ""),
            content=str(t.content),
            similarity=float(t.metadata.get("similarity", 0.0) or 0.0),
            pages=str(t.metadata.get("pages") or ""),
        )
        for t in roadmap.suggested_tasks
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

    form_scores = dict(user_context.form_scores)
    r_app = float(user_context.app_exposure_ratios.get("r_app", 0.0))

    logger.info(
        "Score breakdown user_id=%s session_id=%s gad7_total=%s phq9_total=%s anxiety_p=%.4f depression_p=%.4f severity=%s form_scores=%s r_app=%.4f",
        user_context.user_id,
        session_id,
        gad_total,
        phq_total,
        float(anxiety_probability),
        float(depression_probability),
        severity,
        form_scores,
        float(r_app),
    )

    response = AssessGatewayResponse(
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

    elapsed = time.monotonic() - t0
    logger.info(
        f"{ASSESSMENT_STAGE}.assemble.done",
        user_id=user_context.user_id,
        safety_status=response.safety_status,
        duration_ms=round(elapsed * 1000, 2),
    )
    return response


# ---------------------------------------------------------------------------
# Safe fallback responses
# ---------------------------------------------------------------------------


def _safe_fallback_response(
    user_id: str,
    session_id: Optional[str],
    failed_stage: str,
    answers: Optional[Dict[str, int]] = None,
) -> AssessGatewayResponse:
    """
    Return a degraded but safe response when a stage fails.

    Never exposes stack traces. Sets safety_status to YELLOW with advisory.
    """
    logger.warning(
        f"{ASSESSMENT_STAGE}.fallback.activated",
        user_id=user_id,
        failed_stage=failed_stage,
    )

    advisory_roadmap = FinalRoadmap(
        user_id=user_id,
        overview_paragraph=(
            "We're preparing your personalized roadmap. "
            "Please review your responses and try again shortly, "
            "or reach out to a qualified clinician for support."
        ),
        suggested_tasks=[],
        safety_status="YELLOW",
        next_checkup_days=7,
    )

    answers = answers or {}
    gad_total = gad7_raw_total(answers) if answers else 0
    phq_total = phq9_raw_total(answers) if answers else 0
    anxiety_probability = (
        sigmoid_probability_from_scale_total(gad_total, 21, k=0.05) if answers else 0.0
    )
    depression_probability = (
        sigmoid_probability_from_scale_total(phq_total, 27, k=0.05) if answers else 0.0
    )

    return AssessGatewayResponse(
        **advisory_roadmap.model_dump(),
        anxiety_probability=float(anxiety_probability),
        depression_probability=float(depression_probability),
        severity={
            "anxiety": severity_label_from_gad7_total(gad_total),
            "depression": severity_label_from_phq9_total(phq_total),
        },
        comorbidity="false",
        rag_recommendations=[],
        query_used="fallback",
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Main chain
# ---------------------------------------------------------------------------


def run_assessment_chain(
    user_id: str,
    raw_payload: Any,
    screen_time_minutes: float,
    locale: str = "en",
    session_id: Optional[str] = None,
    answers: Optional[Dict[str, int]] = None,
    top_n: int = 5,
) -> AssessGatewayResponse:
    """
    Execute the full assessment chain:

    1. Profiler  → UserContext
    2. Architect → FinalRoadmap (retrieve + rerank + sequence + overview + audit)
    3. Assemble  → AssessGatewayResponse (with legacy fields)

    Each stage is wrapped in error handling. If a stage fails, a safe
    fallback response is returned — never a stack trace.
    """
    answers = answers or {}
    query_text = ""

    # --- Stage 1: Profiler ---
    try:
        user_context = _run_profiler(user_id, raw_payload, screen_time_minutes)
    except Exception as e:
        logger.error(f"{ASSESSMENT_STAGE}.profiler.error", error=str(e))
        return _safe_fallback_response(user_id, session_id, "profiler", answers)

    # --- Build query text (needed for architect) ---
    try:
        query_text = build_retrieval_query_text(user_context, answers)
    except Exception as e:
        logger.error(f"{ASSESSMENT_STAGE}.query_build.error", error=str(e))
        return _safe_fallback_response(user_id, session_id, "query_build", answers)

    # --- Stage 2: Architect (retrieve → rerank → sequence → audit) ---
    try:
        roadmap = _run_architect(user_context, query_text, locale, top_n)
    except Exception as e:
        logger.error(f"{ASSESSMENT_STAGE}.architect.error", error=str(e))
        return _safe_fallback_response(user_id, session_id, "architect", answers)

    # --- Stage 3: Assemble response ---
    try:
        return _assemble_response(
            roadmap, user_context, answers, query_text, session_id
        )
    except Exception as e:
        logger.error(f"{ASSESSMENT_STAGE}.assemble.error", error=str(e))
        return _safe_fallback_response(user_id, session_id, "assemble", answers)
