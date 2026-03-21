from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Optional

from services.shared.schemas import UserContext


MAX_POINTS_BY_TAG: Dict[str, int] = {
    # Prompt requirement examples.
    "anxiety": 21,  # GAD-7 / 21
    "depression": 27,  # PHQ-9 / 27
}


def _clamp_int(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def sigmoid_r_app(screen_time_minutes: float, *, threshold_minutes: float = 60.0) -> float:
    """
    R_app = 1 / (1 + e^{-0.05 * (minutes - 60)})
    """
    minutes = float(screen_time_minutes)
    z = -0.05 * (minutes - float(threshold_minutes))
    return 1.0 / (1.0 + math.exp(z))


def _infer_answers(raw_forms_json: Any) -> Optional[Dict[str, int]]:
    """
    Best-effort: treat input as:
    - {"answers": {...}} or
    - a raw answers dict with question ids (e.g., gad7_q1, phq9_q1)
    """
    if isinstance(raw_forms_json, dict):
        if isinstance(raw_forms_json.get("answers"), dict):
            return {str(k): int(v) for k, v in raw_forms_json["answers"].items()}
        # If it looks like question ids, assume it's answers directly.
        keys = list(raw_forms_json.keys())
        if any(isinstance(k, str) and ("gad" in k.lower() or "phq" in k.lower()) for k in keys):
            try:
                return {str(k): int(v) for k, v in raw_forms_json.items()}
            except Exception:
                return None
    return None


def _normalize_form_scores(answers: Dict[str, int]) -> Dict[str, int]:
    totals: Dict[str, float] = {"anxiety": 0.0, "depression": 0.0}

    for qid, val in answers.items():
        q = qid.lower()
        v = int(val)
        if "gad" in q:
            totals["anxiety"] += v
        elif "phq" in q:
            totals["depression"] += v

    normalized: Dict[str, int] = {}
    for tag, total in totals.items():
        max_points = MAX_POINTS_BY_TAG.get(tag)
        if not max_points or max_points <= 0:
            continue
        pct = int(round((total / float(max_points)) * 100.0))
        normalized[tag] = _clamp_int(pct, 0, 100)

    # Keep only tags with some signal.
    return {k: v for k, v in normalized.items() if v > 0}


def _extract_suicidal_flag(raw_forms_json: Any) -> bool:
    """
    Best-effort extraction from older repo shapes.

    Example:
      {"risk_flags": {"suicidal": true}}
    """
    if not isinstance(raw_forms_json, dict):
        return False
    rf = raw_forms_json.get("risk_flags")
    if not isinstance(rf, dict):
        return False
    if "suicidal" in rf:
        return bool(rf["suicidal"])
    return False


def build_user_context(
    user_id: str,
    raw_forms_json: Any,
    screen_time_minutes: float,
    user_stats: Optional[Dict[str, int]] = None,
) -> UserContext:
    """
    Build `UserContext` using:
    - Sigmoid normalization for screen time (R_app)
    - Separate normalization of form scores using their known max points
      (e.g., GAD-7 / 21, PHQ-9 / 27)
    """
    timestamp = datetime.now().isoformat()

    # 1) Screen-time derived exposure ratio.
    r_app = sigmoid_r_app(screen_time_minutes, threshold_minutes=60.0)

    # 2) Form scores (normalized using max points).
    answers = _infer_answers(raw_forms_json) or {}
    form_scores = _normalize_form_scores(answers) if answers else {}
    if not form_scores:
        # Safe default so reranking doesn't crash.
        form_scores = {"general": 50}

    # 2.1) Optional safety signal injection (enables auditor to trigger).
    if _extract_suicidal_flag(raw_forms_json):
        form_scores["suicidal"] = 100

    # 3) User stats (default until you specify a policy).
    if user_stats is None:
        avg_form_score = sum(form_scores.values()) / float(max(1, len(form_scores)))
        xp = int(round((r_app * 100.0) + avg_form_score))
        level = 1 + (xp // 200)
        user_stats = {"xp": xp, "level": int(level)}
    else:
        # Ensure required shape.
        user_stats = {str(k): int(v) for k, v in user_stats.items()}

    return UserContext(
        user_id=user_id,
        timestamp=timestamp,
        form_scores=form_scores,
        app_exposure_ratios={"r_app": float(r_app)},
        user_stats=user_stats,
    )

