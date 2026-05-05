import pytest
from uuid import uuid4

from services.auditor.sentiment import SentimentClassifier, detect_frustration
from services.auditor.core import ClinicalAuditor
from services.auditor.schemas import AuditFlags, AuditResult
from services.shared.schemas import ClinicalTask, FinalRoadmap


class TestSentimentClassifier:
    """Tests for SentimentClassifier."""

    @pytest.fixture
    def classifier(self):
        return SentimentClassifier(locale="en")

    def test_no_text_returns_zero(self, classifier):
        assert classifier.classify("") == 0.0
        assert classifier.classify(None) == 0.0

    def test_frustration_keywords_increase_score(self, classifier):
        score = classifier.classify("I am frustrated and stuck")
        assert score > 0.0

    def test_multiple_frustration_keywords(self, classifier):
        score = classifier.classify(
            "I am frustrated and annoyed and confused and overwhelmed"
        )
        assert score > 0.3

    def test_positive_keywords_decrease_score(self, classifier):
        frustration_score = classifier.classify("I am frustrated but thank you")
        assert frustration_score < classifier.classify("I am frustrated")

    def test_score_clamped_to_max(self, classifier):
        high_frustration = (
            "frustrated stuck confused overwhelmed hate terrible awful worst "
            "useless waste pointless hopeless giving up can't do impossible"
        )
        score = classifier.classify(high_frustration)
        assert score <= 1.0

    def test_score_clamped_to_min(self, classifier):
        positive_only = "great helpful useful thank you amazing excellent awesome"
        score = classifier.classify(positive_only)
        assert score >= 0.0

    def test_arabic_keywords(self):
        classifier = SentimentClassifier(locale="ar")
        score = classifier.classify("أنا محبط وغير مفيد")
        assert score > 0.0

    def test_amber_threshold(self, classifier):
        assert classifier.is_amber_advisory(0.8) is True
        assert classifier.is_amber_advisory(0.7) is False
        assert classifier.is_amber_advisory(0.5) is False


class TestDetectFrustration:
    """Tests for convenience function."""

    def test_detect_frustration_basic(self):
        score = detect_frustration("I'm so frustrated and stuck")
        assert score > 0.0

    def test_detect_frustration_locale(self):
        score = detect_frustration("محبط", locale="ar")
        assert score > 0.0


class TestClinicalAuditorFrustration:
    """Tests for ClinicalAuditor integration with sentiment."""

    @pytest.fixture
    def auditor(self):
        return ClinicalAuditor(locale="en")

    @pytest.fixture
    def green_roadmap(self):
        return FinalRoadmap(
            user_id=str(uuid4()),
            overview_paragraph="Great session today, feeling better",
            suggested_tasks=[],
            safety_status="GREEN",
            next_checkup_days=14,
        )

    @pytest.fixture
    def frustrated_roadmap(self):
        return FinalRoadmap(
            user_id=str(uuid4()),
            overview_paragraph="This is useless and frustrating, I hate this",
            suggested_tasks=[],
            safety_status="GREEN",
            next_checkup_days=14,
        )

    def test_green_roadmap_no_frustration(self, auditor, green_roadmap):
        result = auditor.audit(green_roadmap)
        assert result.safety_status == "GREEN"
        assert result.frustration_score == 0.0
        assert result.amber_advisory is False

    def test_frustrated_roadmap_amber_advisory(self, auditor):
        frustrated_roadmap = FinalRoadmap(
            user_id=str(uuid4()),
            overview_paragraph=(
                "This is useless and frustrating, I hate this, I'm stuck, "
                "confused and overwhelmed, fed up, sick of this, it's terrible, "
                "this is the worst, impossible, I'm giving up"
            ),
            suggested_tasks=[],
            safety_status="GREEN",
            next_checkup_days=14,
        )
        result = auditor.audit(frustrated_roadmap)
        assert result.safety_status == "GREEN"
        assert result.frustration_score > 0.0
        assert result.amber_advisory is True

    def test_red_crisis_not_overridden_by_frustration(self, auditor):
        red_roadmap = FinalRoadmap(
            user_id=str(uuid4()),
            overview_paragraph="I want to kill myself",
            suggested_tasks=[],
            safety_status="RED",
            next_checkup_days=1,
        )
        result = auditor.audit(red_roadmap)
        assert result.safety_status == "RED"

    def test_yellow_robotic_with_frustration(self, auditor):
        yellow_roadmap = FinalRoadmap(
            user_id=str(uuid4()),
            overview_paragraph="As an AI language model, I cannot provide medical advice",
            suggested_tasks=[],
            safety_status="YELLOW",
            next_checkup_days=7,
        )
        result = auditor.audit(yellow_roadmap)
        assert result.safety_status == "YELLOW"
        assert result.flags.robotic_tone_detected is True

    def test_audit_flags_include_frustration(self, auditor, frustrated_roadmap):
        result = auditor.audit(frustrated_roadmap)
        assert result.flags.frustration_detected is True
        assert result.flags.frustration_score > 0.0


class TestAuditResultFrustration:
    """Tests for AuditResult schema with frustration fields."""

    def test_audit_result_frustration_fields(self):
        result = AuditResult(
            safety_status="GREEN",
            next_checkup_days=14,
            overview_paragraph="Test",
            task_ids=[],
            frustration_score=0.8,
            amber_advisory=True,
        )
        assert result.frustration_score == 0.8
        assert result.amber_advisory is True

    def test_audit_flags_frustration_fields(self):
        flags = AuditFlags(
            frustration_detected=True,
            frustration_score=0.75,
        )
        assert flags.frustration_detected is True
        assert flags.frustration_score == 0.75
