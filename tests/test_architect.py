from services.architect.auditor import audit_roadmap
from services.architect.pipeline import rerank_tasks, _triple_threat_score
from services.shared.schemas import ClinicalTask, FinalRoadmap, UserContext


def test_triple_threat_score_weights() -> None:
    s = _triple_threat_score(similarity=1.0, form_weight=1.0, r_app=1.0)
    assert abs(s - 1.0) < 1e-9
    s2 = _triple_threat_score(similarity=0.0, form_weight=0.0, r_app=0.0)
    assert abs(s2 - 0.0) < 1e-9


def test_rerank_tasks_orders_by_score() -> None:
    ctx = UserContext(
        user_id="u",
        timestamp="t",
        form_scores={"anxiety": 100},
        app_exposure_ratios={"r_app": 0.5},
        user_stats={},
    )
    low = ClinicalTask(
        task_id="a",
        content="x",
        symptom_tags=["anxiety"],
        difficulty=3,
        xp_reward=10,
        source_reference="s",
        metadata={"similarity": 0.1},
    )
    high = ClinicalTask(
        task_id="b",
        content="y",
        symptom_tags=["anxiety"],
        difficulty=3,
        xp_reward=10,
        source_reference="s",
        metadata={"similarity": 0.9},
    )
    out = rerank_tasks([low, high], ctx, top_n=2)
    assert out[0].task_id == "b"
    assert "triple_threat_score" in out[0].metadata


def test_audit_roadmap_green() -> None:
    r = FinalRoadmap(
        user_id="u",
        overview_paragraph="Here are some next steps for anxiety management.",
        suggested_tasks=[],
        safety_status="GREEN",
        next_checkup_days=14,
    )
    out = audit_roadmap(r)
    assert out.safety_status == "GREEN"


def test_audit_roadmap_red_crisis_keyword() -> None:
    r = FinalRoadmap(
        user_id="u",
        overview_paragraph="I feel suicidal and need help.",
        suggested_tasks=[],
        safety_status="GREEN",
        next_checkup_days=14,
    )
    out = audit_roadmap(r)
    assert out.safety_status == "RED"
    assert out.next_checkup_days == 1
    assert len(out.suggested_tasks) == 1


def test_audit_roadmap_yellow_robotic() -> None:
    r = FinalRoadmap(
        user_id="u",
        overview_paragraph="As an AI language model I cannot diagnose you.",
        suggested_tasks=[],
        safety_status="GREEN",
        next_checkup_days=14,
    )
    out = audit_roadmap(r)
    assert out.safety_status == "YELLOW"
