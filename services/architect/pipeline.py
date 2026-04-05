from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from services.architect.auditor import audit_roadmap
from services.shared.schemas import ClinicalTask, FinalRoadmap, UserContext


def _normalize_similarity(similarity: float) -> float:
    """
    Ensure similarity is in [0..1].
    The current Chroma client often produces similarity in percent [0..100].
    """
    sim = float(similarity)
    if sim > 1.0:
        # Treat values in percent scale.
        sim = sim / 100.0
    if sim < 0.0:
        sim = 0.0
    if sim > 1.0:
        sim = 1.0
    return sim


def _form_weight_from_context(user_context: UserContext, task: ClinicalTask) -> float:
    """
    FormWeight = average of the user's symptom scores that match `task.symptom_tags`.
    We convert normalized form scores (0..100) to 0..1 for the formula.
    """
    matching_scores: List[int] = [
        int(user_context.form_scores[tag]) for tag in task.symptom_tags if tag in user_context.form_scores
    ]
    if not matching_scores:
        return 0.0
    return float(sum(matching_scores) / len(matching_scores)) / 100.0


def _triple_threat_score(similarity: float, form_weight: float, r_app: float) -> float:
    # Score = (Similarity * 0.4) + (FormWeight * 0.3) + (R_app * 0.3)
    return (_normalize_similarity(similarity) * 0.4) + (float(form_weight) * 0.3) + (float(r_app) * 0.3)


def rerank_tasks(
    tasks: Sequence[ClinicalTask],
    user_context: UserContext,
    *,
    top_n: int = 5,
) -> List[ClinicalTask]:
    r_app = float(user_context.app_exposure_ratios.get("r_app", 0.0))

    scored: List[Tuple[float, ClinicalTask]] = []
    for task in tasks:
        sim = float(task.metadata.get("similarity", 0.0))
        form_weight = _form_weight_from_context(user_context, task)
        score = _triple_threat_score(similarity=sim, form_weight=form_weight, r_app=r_app)
        scored.append((score, task))

    scored.sort(key=lambda x: x[0], reverse=True)

    n = max(1, int(top_n))
    top_with_scores = scored[:n]
    top_tasks = [t for _, t in top_with_scores]
    for t, (score, _) in zip(top_tasks, top_with_scores):
        t.metadata["triple_threat_score"] = float(score)
    return top_tasks


def build_overview_paragraph(user_context: UserContext, suggested_tasks: Sequence[ClinicalTask]) -> str:
    top_tags: List[str] = []
    for t in suggested_tasks:
        for tag in t.symptom_tags:
            if tag not in top_tags:
                top_tags.append(tag)
            if len(top_tags) >= 3:
                break
        if len(top_tags) >= 3:
            break

    tags_str = ", ".join(top_tags) if top_tags else "general mental wellness"
    r_app = float(user_context.app_exposure_ratios.get("r_app", 0.0))

    usage_note = (
        "your screen-time pattern suggests higher usage than your threshold"
        if r_app > 0.5
        else "your screen-time pattern is closer to your threshold"
    )

    return (
        f"Based on your responses and {usage_note}, here are tailored next steps focused on {tags_str}. "
        f"Start with the first suggestion today and use the rest as options over the next few days."
    )


def run_architect_pipeline(
    user_context: UserContext,
    candidate_tasks: Sequence[ClinicalTask],
    *,
    top_n: int = 5,
) -> FinalRoadmap:
    suggested = rerank_tasks(candidate_tasks, user_context, top_n=top_n)

    draft = FinalRoadmap(
        user_id=user_context.user_id,
        overview_paragraph=build_overview_paragraph(user_context, suggested),
        suggested_tasks=list(suggested),
        safety_status="GREEN",
        next_checkup_days=14,
    )

    return audit_roadmap(draft)

