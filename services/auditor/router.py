"""
FastAPI router for the Clinical Auditor microservice.

Endpoints:
  POST /audit          — run a full safety audit
  GET  /auditor/health — health check
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.auditor.core import ClinicalAuditor
from services.auditor.schemas import AuditRequest, AuditResult
from services.shared.schemas import ClinicalTask, FinalRoadmap

router = APIRouter(tags=["auditor"])


@router.post("/audit", response_model=AuditResult)
def run_audit(payload: AuditRequest) -> AuditResult:
    """
    Run a clinical safety audit on a roadmap and its tasks.

    Accepts raw task dicts (with at least task_id, content, symptom_tags,
    safety_risk fields) and returns a structured AuditResult.
    """
    auditor = ClinicalAuditor(locale=payload.locale)

    # Reconstruct a minimal FinalRoadmap for the auditor.
    roadmap = FinalRoadmap(
        user_id=payload.user_id,
        overview_paragraph=payload.overview_paragraph,
        suggested_tasks=[],
        safety_status="GREEN",
        next_checkup_days=14,
    )

    # Convert raw dicts to ClinicalTask objects if provided.
    tasks: list[ClinicalTask] = []
    for raw in payload.task_contents:
        try:
            task = ClinicalTask(
                task_id=str(raw.get("task_id", "")),
                content=str(raw.get("content", "")),
                symptom_tags=list(raw.get("symptom_tags", [])),
                difficulty=int(raw.get("difficulty", 3)),
                xp_reward=int(raw.get("xp_reward", 0)),
                safety_risk=bool(raw.get("safety_risk", False)),
                utility_score=float(raw.get("utility_score", 0.5)),
                source_reference=str(raw.get("source_reference", "")),
                metadata=dict(raw.get("metadata", {})),
            )
            tasks.append(task)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task entry: {e}",
            )

    roadmap.suggested_tasks = tasks
    result = auditor.audit(roadmap, tasks=tasks)
    return result


@router.get("/health")
def health_check() -> dict[str, str]:
    """Health check for the auditor service."""
    return {"status": "ok", "service": "auditor"}
