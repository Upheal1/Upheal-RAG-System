from __future__ import annotations

import importlib.util
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.shared.schemas import UserContext


MAX_POINTS_BY_TAG: Dict[str, int] = {
    "anxiety": 21,  # GAD-7 / 21
    "depression": 27,  # PHQ-9 / 27
}

_BAYES_MODULE: Any = None  # None = not loaded, False = unavailable, else module


def _clamp_int(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def _load_assessment_engine():
    """Lazy-load `src/api/assessment_engine.py` without requiring `src.api` package."""
    global _BAYES_MODULE
    if _BAYES_MODULE is False:
        return None
    if _BAYES_MODULE is not None:
        return _BAYES_MODULE
    repo = Path(__file__).resolve().parents[2]
    path = repo / "src" / "api" / "assessment_engine.py"
    if not path.is_file():
        _BAYES_MODULE = False
        return None
    spec = importlib.util.spec_from_file_location("upheal_assessment_engine", path)
    if spec is None or spec.loader is None:
        _BAYES_MODULE = False
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _BAYES_MODULE = mod
    return mod


def sigmoid_r_app(screen_time_minutes: float, *, threshold_minutes: float = 60.0) -> float:
    """
    R_app = 1 / (1 + e^{-0.05 * (minutes - 60)})
    """
    minutes = float(screen_time_minutes)
    z = -0.05 * (minutes - float(threshold_minutes))
    return 1.0 / (1.0 + math.exp(z))


def infer_answers_dict(raw_forms_json: Any) -> Optional[Dict[str, int]]:
    """
    Extract answers from supported payload shapes:
    - {"answers": {...}}
    - flat dict with gad/phq-like question ids
    """
    if isinstance(raw_forms_json, dict):
        if isinstance(raw_forms_json.get("answers"), dict):
            return {str(k): int(v) for k, v in raw_forms_json["answers"].items()}
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

    return {k: v for k, v in normalized.items() if v > 0}


def _merge_scale_and_bayesian(answers: Dict[str, int]) -> Dict[str, int]:
    """
    Blend scale-based 0..100 scores with Bayesian path probabilities (0..1 → 0..100).
    """
    scale = _normalize_form_scores(answers)
    mod = _load_assessment_engine()
    if not mod or not answers:
        return scale

    br = mod.run_assessment(answers)
    bayes_anx = _clamp_int(int(round(float(br["anxiety_probability"]) * 100.0)), 0, 100)
    bayes_dep = _clamp_int(int(round(float(br["depression_probability"]) * 100.0)), 0, 100)

    merged: Dict[str, int] = {}
    for tag, bscore in (("anxiety", bayes_anx), ("depression", bayes_dep)):
        s = scale.get(tag)
        if s is not None:
            merged[tag] = _clamp_int(int(round(0.55 * float(s) + 0.45 * float(bscore))), 0, 100)
        elif bscore >= 5:
            merged[tag] = bscore

    if not merged:
        return scale if scale else {}
    return merged


def _extract_suicidal_flag(raw_forms_json: Any) -> bool:
    if not isinstance(raw_forms_json, dict):
        return False
    rf = raw_forms_json.get("risk_flags")
    if not isinstance(rf, dict):
        return False
    if "suicidal" in rf:
        return bool(rf["suicidal"])
    return False


def build_retrieval_query_text(user_context: UserContext, answers: Dict[str, int]) -> str:
    """
    Natural-language query for embedding search: prefer Bayesian `generate_rag_query`
    output when we have item-level answers; otherwise derive from form_scores severities.
    """
    mod = _load_assessment_engine()
    if mod and answers:
        try:
            return str(mod.run_assessment(answers)["query"])
        except Exception:
            pass

    parts: list[str] = []
    for tag, score in user_context.form_scores.items():
        if tag in ("general", "suicidal"):
            continue
        if score >= 70:
            sev = "severe"
        elif score >= 40:
            sev = "moderate"
        else:
            sev = "mild"
        parts.append(f"{tag} {sev} clinical psychology interventions evidence-based")

    if not parts:
        return "mental health wellness preventive strategies self-care"
    return " ".join(parts)


def build_user_context(
    user_id: str,
    raw_forms_json: Any,
    screen_time_minutes: float,
    user_stats: Optional[Dict[str, int]] = None,
) -> UserContext:
    """
    Build `UserContext` using sigmoid R_app and form scores (scale + optional Bayesian blend).
    """
    timestamp = datetime.now().isoformat()
    r_app = sigmoid_r_app(screen_time_minutes, threshold_minutes=60.0)

    answers = infer_answers_dict(raw_forms_json) or {}
    if answers:
        form_scores = _merge_scale_and_bayesian(answers)
    else:
        form_scores = {}

    if not form_scores:
        form_scores = {"general": 50}

    if _extract_suicidal_flag(raw_forms_json):
        form_scores["suicidal"] = 100

    if user_stats is None:
        avg_form_score = sum(form_scores.values()) / float(max(1, len(form_scores)))
        xp = int(round((r_app * 100.0) + avg_form_score))
        level = 1 + (xp // 200)
        user_stats = {"xp": xp, "level": int(level)}
    else:
        user_stats = {str(k): int(v) for k, v in user_stats.items()}

    return UserContext(
        user_id=user_id,
        timestamp=timestamp,
        form_scores=form_scores,
        app_exposure_ratios={"r_app": float(r_app)},
        user_stats=user_stats,
    )
