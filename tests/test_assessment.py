from services.assessment.core import (
    build_retrieval_query_text,
    build_user_context,
    infer_answers_dict,
    sigmoid_r_app,
)
from services.shared.schemas import UserContext


def test_sigmoid_r_app_at_threshold() -> None:
    # minutes == 60 -> z=0 -> sigmoid 0.5
    assert abs(sigmoid_r_app(60.0) - 0.5) < 1e-9


def test_sigmoid_r_app_uses_math_exp_shape() -> None:
    low = sigmoid_r_app(0.0)
    high = sigmoid_r_app(200.0)
    assert 0.0 < low < 0.5
    assert 0.5 < high < 1.0


def test_infer_answers_nested() -> None:
    raw = {"answers": {"gad7_q1": 2, "phq9_q1": 1}}
    assert infer_answers_dict(raw) == {"gad7_q1": 2, "phq9_q1": 1}


def test_build_user_context_default_general() -> None:
    ctx = build_user_context("u1", {}, 0.0)
    assert ctx.user_id == "u1"
    assert "general" in ctx.form_scores
    assert "r_app" in ctx.app_exposure_ratios


def test_build_retrieval_query_text_from_scores() -> None:
    ctx = UserContext(
        user_id="u",
        timestamp="t",
        form_scores={"anxiety": 80, "depression": 10},
        app_exposure_ratios={},
        user_stats={},
    )
    q = build_retrieval_query_text(ctx, {})
    assert "anxiety" in q.lower()
    assert "severe" in q or "moderate" in q or "mild" in q
