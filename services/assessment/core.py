from __future__ import annotations

import importlib.util
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    # Prefer FastAPI's exception type when available (gateway runtime).
    from fastapi import HTTPException  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    class HTTPException(Exception):
        """
        Lightweight fallback for environments where FastAPI isn't installed.

        Provides `status_code` and `detail` attributes compatible with how this
        module is used in unit tests and by the gateway when FastAPI is present.
        """

        def __init__(self, status_code: int, detail: Any):
            super().__init__(detail)
            self.status_code = int(status_code)
            self.detail = detail

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


def sigmoid_probability_from_scale_total(
    total: int,
    max_scale: int,
    *,
    k: float = 0.05,
) -> float:
    """
    Convert a raw PHQ/GAD scale total into a pseudo-probability via a sigmoid.

    We use the same steepness constant as `sigmoid_r_app` (k=0.05) and center
    the curve at half the max scale.
    """
    t = float(int(total))
    m = float(int(max_scale))
    midpoint = m / 2.0
    z = -float(k) * (t - midpoint)
    return 1.0 / (1.0 + math.exp(z))


_GAD7_RE = re.compile(r"^gad7_q([1-7])$", re.IGNORECASE)
_PHQ9_RE = re.compile(r"^phq9_q([1-9])$", re.IGNORECASE)


def _coerce_item_score(v: Any) -> Optional[int]:
    """Coerce an item score to int in [0..3]; return None if invalid."""
    try:
        iv = int(v)
    except Exception:
        return None
    if 0 <= iv <= 3:
        return iv
    return None


def validate_phq9_gad7_answers(answers: Dict[str, int]) -> None:
    """
    Strict clinical validation:
    - If any GAD-7/PHQ-9 item id is present, require complete sets:
      gad7_q1..gad7_q7 and phq9_q1..phq9_q9.
    - Values must be integers 0..3.
    - Any key that contains 'gad'/'phq' but doesn't match expected ids fails fast.
    """
    gad_items: Dict[int, int] = {}
    phq_items: Dict[int, int] = {}
    unknown_scale_keys: list[str] = []

    for k, v in (answers or {}).items():
        ks = str(k)
        m_gad = _GAD7_RE.match(ks)
        m_phq = _PHQ9_RE.match(ks)
        if m_gad:
            gad_items[int(m_gad.group(1))] = int(v)
            continue
        if m_phq:
            phq_items[int(m_phq.group(1))] = int(v)
            continue
        if "gad" in ks.lower() or "phq" in ks.lower():
            unknown_scale_keys.append(ks)

    if unknown_scale_keys:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_scale_item_ids",
                "message": "GAD/PHQ-like keys must match gad7_q1..gad7_q7 and phq9_q1..phq9_q9.",
                "keys": sorted(set(unknown_scale_keys)),
            },
        )

    if not gad_items and not phq_items:
        return

    missing_gad = [f"gad7_q{i}" for i in range(1, 8) if i not in gad_items]
    missing_phq = [f"phq9_q{i}" for i in range(1, 10) if i not in phq_items]
    if missing_gad or missing_phq:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "incomplete_scale",
                "message": "Strict validation requires full GAD-7 (7 items) and PHQ-9 (9 items) when any scale item is present.",
                "missing": missing_gad + missing_phq,
            },
        )

    bad_vals: list[str] = []
    for i in range(1, 8):
        v = gad_items[i]
        if not (0 <= int(v) <= 3):
            bad_vals.append(f"gad7_q{i}={v}")
    for i in range(1, 10):
        v = phq_items[i]
        if not (0 <= int(v) <= 3):
            bad_vals.append(f"phq9_q{i}={v}")
    if bad_vals:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_item_values",
                "message": "PHQ-9 and GAD-7 item values must be integers in range 0..3.",
                "items": bad_vals,
            },
        )


def gad7_raw_total(answers: Dict[str, int]) -> int:
    return sum(int(answers.get(f"gad7_q{i}", 0)) for i in range(1, 8))


def phq9_raw_total(answers: Dict[str, int]) -> int:
    return sum(int(answers.get(f"phq9_q{i}", 0)) for i in range(1, 10))


def severity_label_from_gad7_total(gad7_total: int) -> str:
    # Requested rule: >15 Severe, >10 Moderate, else Mild.
    t = int(gad7_total)
    if t > 15:
        return "Severe"
    if t > 10:
        return "Moderate"
    return "Mild"


def severity_label_from_phq9_total(phq9_total: int) -> str:
    # Common PHQ-9 cutoffs: 0-9 Mild, 10-19 Moderate, 20-27 Severe.
    t = int(phq9_total)
    if t >= 20:
        return "Severe"
    if t >= 10:
        return "Moderate"
    return "Mild"


def infer_answers_dict(raw_forms_json: Any) -> Optional[Dict[str, int]]:
    """
    Extract answers from supported payload shapes:
    - {"answers": {...}}
    - flat dict with gad/phq-like question ids
    """
    if isinstance(raw_forms_json, dict):
        if isinstance(raw_forms_json.get("answers"), dict):
            out: Dict[str, int] = {}
            for k, v in raw_forms_json["answers"].items():
                iv = _coerce_item_score(v)
                if iv is None:
                    continue
                out[str(k)] = iv
            return out
        keys = list(raw_forms_json.keys())
        if any(isinstance(k, str) and ("gad" in k.lower() or "phq" in k.lower()) for k in keys):
            out2: Dict[str, int] = {}
            for k, v in raw_forms_json.items():
                iv = _coerce_item_score(v)
                if iv is None:
                    continue
                out2[str(k)] = iv
            return out2
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
    validate_phq9_gad7_answers(answers)
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
