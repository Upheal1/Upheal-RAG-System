"""
Sentiment classifier for detecting user frustration in chat feedback.

Lightweight keyword-based approach that returns a frustration_score (0.0-1.0).
Used by ClinicalAuditor to set AMBER advisory when frustration > 0.7.
"""

from __future__ import annotations

from typing import List


class SentimentClassifier:
    """
    Stateless sentiment classifier for detecting frustration in text.

    Uses keyword matching with weighted scoring to estimate frustration level.
    Does NOT override crisis detection - RED path always wins.
    """

    FRUSTRATION_KEYWORDS_EN = [
        "frustrated",
        "annoyed",
        "stuck",
        "confused",
        "overwhelmed",
        "hate",
        "terrible",
        "awful",
        "worst",
        "useless",
        "waste",
        "pointless",
        "hopeless",
        "giving up",
        "can't do",
        "impossible",
        "fed up",
        "sick of",
        "done with",
        "ridiculous",
        "angry",
        "irritated",
    ]

    FRUSTRATION_KEYWORDS_AR = [
        "محبط",
        "مضطر",
        "فاشل",
        "غير مفيد",
        "سيء",
        "أسوأ",
        "مستحيل",
        "غير قادر",
        "متضايق",
    ]

    POSITIVE_KEYWORDS_EN = [
        "great",
        "helpful",
        "useful",
        "thank",
        "better",
        "good",
        "amazing",
        "excellent",
        "awesome",
        "love",
        "appreciate",
        "perfect",
    ]

    POSITIVE_KEYWORDS_AR = [
        "مفيد",
        "شكرا",
        "ممتاز",
        "رائع",
        "ممتاز",
        "حب",
    ]

    FRUSTRATION_WEIGHT = 0.15
    POSITIVE_WEIGHT = 0.1
    MAX_SCORE = 1.0
    AMBER_THRESHOLD = 0.7

    def __init__(self, locale: str = "en") -> None:
        self._locale = locale

    @property
    def frustration_keywords(self) -> List[str]:
        if self._locale == "ar":
            return self.FRUSTRATION_KEYWORDS_AR + self.FRUSTRATION_KEYWORDS_EN
        return self.FRUSTRATION_KEYWORDS_EN

    @property
    def positive_keywords(self) -> List[str]:
        if self._locale == "ar":
            return self.POSITIVE_KEYWORDS_AR + self.POSITIVE_KEYWORDS_EN
        return self.POSITIVE_KEYWORDS_EN

    def classify(self, text: str) -> float:
        """
        Calculate frustration score from text.

        Returns:
            float: frustration_score between 0.0 and 1.0

        Scoring:
        - Each frustration keyword adds FRUSTRATION_WEIGHT
        - Each positive keyword subtracts POSITIVE_WEIGHT
        - Clamped to [0.0, 1.0]
        """
        if not text:
            return 0.0

        lower_text = text.lower()

        frustration_count = sum(
            1 for kw in self.frustration_keywords if kw.lower() in lower_text
        )
        positive_count = sum(
            1 for kw in self.positive_keywords if kw.lower() in lower_text
        )

        score = (frustration_count * self.FRUSTRATION_WEIGHT) - (
            positive_count * self.POSITIVE_WEIGHT
        )

        return max(0.0, min(self.MAX_SCORE, score))

    def is_amber_advisory(self, frustration_score: float) -> bool:
        """Check if frustration score exceeds AMBER threshold."""
        return frustration_score > self.AMBER_THRESHOLD


def detect_frustration(text: str, locale: str = "en") -> float:
    """
    Convenience function for one-off sentiment classification.

    Args:
        text: Text to analyze
        locale: Language code (en/ar)

    Returns:
        frustration_score between 0.0 and 1.0
    """
    classifier = SentimentClassifier(locale=locale)
    return classifier.classify(text)
