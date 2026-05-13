from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from services.architect.auditor import audit_roadmap
from services.architect.director_override import (
    apply_directive_constraints,
    load_active_directive,
)
from services.shared.logging import get_logger
from services.shared.schemas import (
    AppPercentage,
    ClinicalTask,
    FinalRoadmap,
    RetrievalQuery,
    RoadmapDay,
    UserContext,
)

if TYPE_CHECKING:
    from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase

logger = get_logger(__name__)


def _normalize_similarity(similarity: float) -> float:
    sim = float(similarity)
    if sim > 1.0:
        sim = sim / 100.0
    if sim < 0.0:
        sim = 0.0
    if sim > 1.0:
        sim = 1.0
    return sim


def _jaccard_overlap(task_tags: List[str], user_domains: set[str]) -> float:
    task_set = {tag.lower() for tag in task_tags}
    if not task_set and not user_domains:
        return 0.0
    intersection = task_set & user_domains
    union = task_set | user_domains
    if not union:
        return 0.0
    return len(intersection) / len(union)


def _form_weight_from_context(user_context: UserContext, task: ClinicalTask) -> float:
    user_domains = {tag.lower() for tag in user_context.form_scores.keys()}
    return _jaccard_overlap(task.symptom_tags, user_domains)


_DETOX_BOOST_TAGS = {
    "grounding",
    "breathing",
    "somatic",
    "mindfulness",
    "relaxation",
    "digital-detox",
}

_DETOX_BOOST_FACTOR = 0.15


def _apply_detox_boost(score: float, task: ClinicalTask, boost: bool) -> float:
    if not boost:
        return score
    task_tags_lower = {tag.lower() for tag in task.symptom_tags}
    if task_tags_lower & _DETOX_BOOST_TAGS:
        return score * (1.0 + _DETOX_BOOST_FACTOR)
    return score


def _triple_threat_score(
    similarity: float,
    form_weight: float,
    r_app: float,
    utility_score: float = 0.5,
) -> float:
    normalized_utility = max(0.0, min(1.0, float(utility_score)))
    return (
        (_normalize_similarity(similarity) * 0.35)
        + (float(form_weight) * 0.25)
        + (float(r_app) * 0.25)
        + (normalized_utility * 0.15)
    )


def _get_user_level(user_context: UserContext) -> int:
    return int(user_context.user_stats.get("level", 1))


def _apply_difficulty_filter(
    tasks: Sequence[ClinicalTask], max_difficulty: int, user_level: int
) -> List[ClinicalTask]:
    effective_max = min(max_difficulty, user_level)
    return [t for t in tasks if t.difficulty <= effective_max]


def _apply_symptom_overlap_filter(
    tasks: Sequence[ClinicalTask], symptom_keywords: List[str]
) -> List[ClinicalTask]:
    if not symptom_keywords:
        return list(tasks)

    keywords_lower = {kw.lower() for kw in symptom_keywords}
    filtered = []
    for task in tasks:
        task_tags_lower = {tag.lower() for tag in task.symptom_tags}
        if task_tags_lower & keywords_lower:
            filtered.append(task)
    return filtered


def _load_fallback_candidates(retrieval_query: RetrievalQuery) -> List[ClinicalTask]:
    from tests.fixtures.clinical_tasks import SAMPLE_TASKS

    n = retrieval_query.candidate_count
    return SAMPLE_TASKS[:n]


def retrieve_candidates(
    user_context: UserContext,
    retrieval_query: RetrievalQuery,
    *,
    chroma_kb: Optional[ChromaKnowledgeBase] = None,
) -> List[ClinicalTask]:
    """
    Fetch candidates from the knowledge base, apply difficulty and
    symptom-tag overlap filters, and return the filtered list.

    Falls back to hardcoded fixtures when chroma_kb is unavailable or unhealthy.
    Logs the retrieval query text for debugging.
    """
    query_text = retrieval_query.query_text or ", ".join(
        retrieval_query.symptom_keywords or ["general"]
    )

    logger.info(
        "architect.pipeline.retrieve_candidates.start",
        query_text=query_text,
        symptom_keywords=retrieval_query.symptom_keywords,
        max_difficulty=retrieval_query.max_difficulty,
        boost_digital_detox=retrieval_query.boost_digital_detox,
        candidate_count=retrieval_query.candidate_count,
        user_level=_get_user_level(user_context),
    )

    raw_tasks: List[ClinicalTask] = []

    if chroma_kb is not None and chroma_kb.is_healthy():
        raw_tasks = chroma_kb.retrieve_tasks(
            user_context,
            query_text=query_text,
            top_k=retrieval_query.candidate_count,
        )
        logger.info(
            "architect.pipeline.retrieve_candidates.chroma_success",
            fetched_count=len(raw_tasks),
            query_text=query_text,
        )
    else:
        raw_tasks = _load_fallback_candidates(retrieval_query)
        logger.info(
            "architect.pipeline.retrieve_candidates.fixture_fallback",
            fallback_count=len(raw_tasks),
            query_text=query_text,
        )

    user_level = _get_user_level(user_context)
    filtered = _apply_difficulty_filter(
        raw_tasks, retrieval_query.max_difficulty, user_level
    )
    filtered = _apply_symptom_overlap_filter(filtered, retrieval_query.symptom_keywords)

    logger.info(
        "architect.pipeline.retrieve_candidates.done",
        raw_count=len(raw_tasks),
        after_difficulty_filter=len(filtered),
        query_text=query_text,
    )

    return filtered


def _calculate_social_heavy_penalty(app_breakdown: List[AppPercentage]) -> float:
    """
    If social apps > 30% of total screen time, return boost factor.
    If productivity apps > 50%, return reduced boost factor.
    """
    total_social_pct = sum(
        app.percentage
        for app in app_breakdown
        if app.category == "social"
    )

    total_productivity_pct = sum(
        app.percentage
        for app in app_breakdown
        if app.category == "productivity"
    )

    if total_social_pct > 30.0:
        return 1.15  # Boost detox by 15%
    elif total_productivity_pct > 50.0:
        return 0.85  # Reduce detox boost by 15%
    else:
        return 1.0


def rerank_tasks(
    tasks: Sequence[ClinicalTask],
    user_context: UserContext,
    *,
    top_n: int = 5,
    boost_digital_detox: bool = False,
) -> List[ClinicalTask]:
    r_app = float(user_context.app_exposure_ratios.get("r_app", 0.0))

    # Calculate social/productivity penalty from app breakdown
    social_penalty = 1.0
    if user_context.screen_time_data is not None:
        from services.assessment.core import parse_screen_time_data
        parsed = parse_screen_time_data(user_context.screen_time_data)
        app_breakdown = [
            AppPercentage(**app) for app in parsed.get("app_breakdown", [])
        ]
        social_penalty = _calculate_social_heavy_penalty(app_breakdown)

    scored: List[Tuple[float, ClinicalTask]] = []
    for task in tasks:
        sim = float(task.metadata.get("similarity", 0.0))
        form_weight = _form_weight_from_context(user_context, task)
        utility_score = getattr(task, "utility_score", 0.5)
        base_score = _triple_threat_score(
            similarity=sim,
            form_weight=form_weight,
            r_app=r_app,
            utility_score=utility_score,
        )

        # Apply detox boost with social penalty
        if boost_digital_detox:
            final_score = _apply_detox_boost(base_score * social_penalty, task, boost_digital_detox)
        else:
            final_score = base_score

        scored.append((final_score, task))

    scored.sort(key=lambda x: (x[0], -x[1].difficulty, x[1].task_id), reverse=True)

    n = max(1, int(top_n))
    top_with_scores = scored[:n]
    top_tasks = [t for _, t in top_with_scores]
    for t, (score, _) in zip(top_tasks, top_with_scores):
        t.metadata["triple_threat_score"] = float(score)
    return top_tasks


def _sequence_tasks(
    tasks: Sequence[ClinicalTask],
    user_context: UserContext,
) -> List[ClinicalTask]:
    """
    Minimal Gamifier: sort by difficulty ascending and assign phase labels.

    Phase assignment:
    - difficulty 1-2 → Quick Win
    - difficulty 3 → Ladder
    - difficulty 4-5 → Boss

    This hook is reserved for A-YAH-06 (full Gamifier) which will add
    XP scaling and more sophisticated sequencing.
    """
    sorted_tasks = sorted(list(tasks), key=lambda t: (t.difficulty, -t.utility_score))

    for task in sorted_tasks:
        if task.difficulty <= 2:
            task.phase = "Quick Win"
        elif task.difficulty == 3:
            task.phase = "Ladder"
        else:
            task.phase = "Boss"

    return sorted_tasks


def generate_ninety_day_plan(
    candidates: List[ClinicalTask],
    user_context: UserContext,
    total_days: int = 90,
) -> List[RoadmapDay]:
    """
    Generate a 90-day roadmap with 1 task per day.

    Phase allocation:
      Days 1-7   → Quick Win  (difficulty 1-2)
      Days 8-30  → Ladder     (difficulty 3)
      Days 31-90 → Boss       (difficulty 4-5)

    When unique tasks are exhausted within a phase, repeat with
    day-specific context labels to give each repetition a fresh lens.
    """
    PHASES = [
        ("Quick Win", 1, 7, [1, 2]),    # days 1-7, difficulty 1-2
        ("Ladder", 8, 30, [3]),           # days 8-30, difficulty 3
        ("Boss", 31, 90, [4, 5]),         # days 31-90, difficulty 4-5
    ]

    DAY_CONTEXTS = [
        "morning routine",
        "midday check-in",
        "evening wind-down",
        "stress relief",
        "focus boost",
        "pre-sleep calm",
        "weekend reset",
        "commute companion",
        "mindful break",
    ]

    days = []
    for phase_name, start_day, end_day, difficulties in PHASES:
        phase_candidates = [t for t in candidates if t.difficulty in difficulties]

        # Fallback: if no candidates match this phase's difficulty,
        # use all candidates (don't leave days empty)
        if not phase_candidates:
            phase_candidates = list(candidates)

        day_in_phase = 0
        for day_num in range(start_day, end_day + 1):
            # Cycle through candidates with rotation
            idx = day_in_phase % len(phase_candidates)
            task = phase_candidates[idx]

            # Apply day context for variety when repeating
            context_idx = day_in_phase % len(DAY_CONTEXTS)

            days.append(
                RoadmapDay(
                    day_number=day_num,
                    task=task,
                    phase=phase_name,
                    day_context=DAY_CONTEXTS[context_idx],
                )
            )
            day_in_phase += 1

    return days


def build_overview_paragraph(
    user_context: UserContext, suggested_tasks: Sequence[ClinicalTask]
) -> str:
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
    candidate_tasks: Optional[Sequence[ClinicalTask]] = None,
    *,
    retrieval_query: Optional[RetrievalQuery] = None,
    chroma_kb: Optional[ChromaKnowledgeBase] = None,
    top_n: int = 5,
    locale: str = "en",
) -> FinalRoadmap:
    if candidate_tasks is not None:
        pre_filtered = list(candidate_tasks)
    else:
        rq = retrieval_query or RetrievalQuery()

        directive = load_active_directive(user_context.user_id)
        if directive is not None:
            rq = apply_directive_constraints(directive, rq)

        pre_filtered = retrieve_candidates(user_context, rq, chroma_kb=chroma_kb)

    if not pre_filtered:
        rq = retrieval_query or RetrievalQuery()
        pre_filtered = _load_fallback_candidates(rq)

    rq = retrieval_query or RetrievalQuery()
    suggested = rerank_tasks(
        pre_filtered,
        user_context,
        top_n=top_n,
        boost_digital_detox=rq.boost_digital_detox,
    )

    # Gamifier slot (A-YAH-06) — pass-through for now.
    suggested = _sequence_tasks(suggested, user_context)

    # Generate 90-day plan from all candidates (not just top_n)
    ninety_day_plan = generate_ninety_day_plan(
        list(pre_filtered),
        user_context,
        total_days=90,
    )

    # Determine next checkup based on current phase (first day = Quick Win)
    next_checkup = 7  # Quick Win phase checkup

    draft = FinalRoadmap(
        user_id=user_context.user_id,
        overview_paragraph=build_overview_paragraph(user_context, suggested),
        suggested_tasks=list(suggested),
        safety_status="GREEN",
        next_checkup_days=next_checkup,
        days=ninety_day_plan,
        total_days=90,
        assessment_required=False,
    )

    resolved_locale = retrieval_query.locale if retrieval_query else locale
    return audit_roadmap(draft, locale=resolved_locale)
