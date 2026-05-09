"""
Gateway orchestrator — wires Profiler → Architect → Auditor into a single
assessment chain with per-stage logging, timing, and safe error handling.

The Gamifier (A-YAH-06) slot is reserved as a no-op hook for later insertion.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.architect.pipeline import run_architect_pipeline
from services.assessment.core import (
    build_retrieval_query_text,
    build_screen_time_insights,
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
    ScreenTimeData,
    UserContext,
)

logger = get_logger(__name__)
_kb = ChromaKnowledgeBase()

ASSESSMENT_STAGE = "gateway.assess"


def _persist_assessment_to_supabase(
    user_id: str,
    response: AssessGatewayResponse,
    answers: Dict[str, int],
    screen_time_minutes: float,
) -> None:
    """
    Fire-and-forget Supabase post-writes for assessment_responses,
    roadmaps, and roadmap_tasks. Never blocks or breaks the response.
    """
    try:
        from services.shared.state import SupabaseSyncHook

        assessment_hook = SupabaseSyncHook("assessment_responses")
        row = {
            "user_id": str(uuid.uuid5(uuid.NAMESPACE_URL, user_id)),
            "locale": "en",
            "form_payload": {"answers": answers},
            "gad7_score": gad7_raw_total(answers) if answers else 0,
            "phq9_score": phq9_raw_total(answers) if answers else 0,
            "screen_time_minutes": int(screen_time_minutes),
        }
        assessment_hook.insert_row(row)
        logger.info(
            "orchestrator.persist.assessment_responses",
            user_id=user_id,
        )
    except Exception as e:
        logger.warning(
            "orchestrator.persist.assessment_responses.failed",
            user_id=user_id,
            error=str(e),
        )

    try:
        from services.shared.state import SupabaseSyncHook

        roadmap_hook = SupabaseSyncHook("roadmaps")
        user_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, user_id))

        existing = roadmap_hook.fetch_one({"user_id": user_uuid})
        generation_number = 1
        if existing and "generation_number" in existing:
            generation_number = int(existing["generation_number"]) + 1

        roadmap_row = {
            "user_id": user_uuid,
            "generation_number": generation_number,
            "overall_theme": response.safety_status,
            "status": "ACTIVE",
        }
        roadmap_result = roadmap_hook.insert_row(roadmap_row)
        roadmap_id = roadmap_result.get("id")

        if roadmap_id and response.suggested_tasks:
            tasks_hook = SupabaseSyncHook("roadmap_tasks")
            for idx, task in enumerate(response.suggested_tasks):
                task_row = {
                    "roadmap_id": roadmap_id,
                    "task_id": str(uuid.uuid5(uuid.NAMESPACE_URL, task.task_id)),
                    "sequence_order": idx,
                    "xp_earned": task.xp_reward,
                    "status": "ASSIGNED",
                }
                try:
                    tasks_hook.insert_row(task_row)
                except Exception:
                    pass

        logger.info(
            "orchestrator.persist.roadmaps",
            user_id=user_id,
            generation_number=generation_number,
            task_count=len(response.suggested_tasks),
        )
    except Exception as e:
        logger.warning(
            "orchestrator.persist.roadmaps.failed",
            user_id=user_id,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Gamifier hook (no-op placeholder — A-YAH-06)
# ---------------------------------------------------------------------------


def _sequence_tasks(
    tasks: list,
    user_context: UserContext,
) -> list:
    """
    Minimal Gamifier: sort by difficulty ascending and assign phase labels.

    Phase assignment:
    - difficulty 1-2 → Quick Win
    - difficulty 3 → Ladder
    - difficulty 4-5 → Boss

    This hook is reserved for A-YAH-06 (full Gamifier) which will add
    XP scaling and more sophisticated sequencing.
    """
    sorted_tasks = sorted(tasks, key=lambda t: (t.difficulty, -t.utility_score))

    for task in sorted_tasks:
        if task.difficulty <= 2:
            task.phase = "Quick Win"
        elif task.difficulty == 3:
            task.phase = "Ladder"
        else:
            task.phase = "Boss"

    return sorted_tasks


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


def _run_profiler(
    user_id: str,
    raw_payload: Any,
    screen_time_minutes: float,
    screen_time_data: Optional[ScreenTimeData] = None,
) -> UserContext:
    t0 = time.monotonic()
    logger.info(f"{ASSESSMENT_STAGE}.profiler.start", user_id=user_id)

    ctx = build_user_context(
        user_id=user_id,
        raw_forms_json=raw_payload,
        screen_time_minutes=screen_time_minutes,
        screen_time_data=screen_time_data,
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

    screen_time_insights = None
    if user_context.screen_time_data is not None:
        try:
            screen_time_insights = build_screen_time_insights(user_context.screen_time_data)
        except Exception:
            screen_time_insights = None

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
        screen_time_insights=screen_time_insights,
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
    screen_time_data: Optional[ScreenTimeData] = None,
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
        user_context = _run_profiler(user_id, raw_payload, screen_time_minutes, screen_time_data)
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
        response = _assemble_response(
            roadmap, user_context, answers, query_text, session_id
        )
    except Exception as e:
        logger.error(f"{ASSESSMENT_STAGE}.assemble.error", error=str(e))
        return _safe_fallback_response(user_id, session_id, "assemble", answers)

    # --- Post-write to Supabase (fire-and-forget in background) ---
    try:
        persist_thread = threading.Thread(
            target=_persist_assessment_to_supabase,
            args=(user_id, response, answers, screen_time_minutes),
            daemon=True,
        )
        persist_thread.start()
    except Exception as e:
        logger.warning("orchestrator.persist.spawn_failed", error=str(e))

    return response
