from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ScreenTimeAppUsage(BaseModel):
    packageName: str
    usageTime: int = 0
    category: str = "other"


class ScreenTimeData(BaseModel):
    totalMinutes: float = 0.0
    socialMinutes: float = 0.0
    productivityMinutes: float = 0.0
    dailyUsage: List[ScreenTimeAppUsage] = Field(default_factory=list)

    @property
    def social_ratio(self) -> float:
        total = self.totalMinutes
        if total <= 0:
            return 0.0
        return min(self.socialMinutes / total, 1.0)

    @property
    def productivity_ratio(self) -> float:
        total = self.totalMinutes
        if total <= 0:
            return 0.0
        return min(self.productivityMinutes / total, 1.0)


class RetrievalQuery(BaseModel):
    """
    Controls what the architect pipeline retrieves from the knowledge base.
    """

    symptom_keywords: List[str] = Field(default_factory=list)
    max_difficulty: int = Field(default=5, ge=1, le=5)
    boost_digital_detox: bool = False
    candidate_count: int = Field(default=10, ge=1)
    locale: str = "en"
    query_text: Optional[str] = None


class ClinicalTask(BaseModel):
    """
    A single actionable clinical-style recommendation candidate.
    """

    task_id: str
    content: str
    symptom_tags: List[str]
    difficulty: int = Field(..., ge=1, le=5)
    xp_reward: int
    safety_risk: bool = False
    utility_score: float = 0.5
    source_reference: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    phase: Literal["Quick Win", "Ladder", "Boss"] = "Quick Win"


class UserContext(BaseModel):
    user_id: str
    timestamp: str
    form_scores: Dict[str, int] = Field(default_factory=dict)
    app_exposure_ratios: Dict[str, float] = Field(default_factory=dict)
    user_stats: Dict[str, int] = Field(default_factory=dict)
    screen_time_data: Optional[ScreenTimeData] = None


class FinalRoadmap(BaseModel):
    user_id: str
    overview_paragraph: str
    suggested_tasks: List[ClinicalTask] = Field(default_factory=list)
    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int


class LegacyRAGRecommendation(BaseModel):
    """
    Legacy Flutter/API shape for a single RAG hit.
    Mirrors `src/api/models.py:RAGRecommendation`.
    """

    source: str
    section: str
    content: str
    similarity: float
    pages: str


class ScreenTimeInsights(BaseModel):
    totalMinutes: float = 0.0
    socialRatio: float = 0.0
    productivityRatio: float = 0.0
    topSocialApps: List[str] = Field(default_factory=list)
    topProductivityApps: List[str] = Field(default_factory=list)


class AssessGatewayResponse(FinalRoadmap):
    """
    `POST /api/assess` response: full roadmap plus legacy clinical/RAG fields.
    """

    anxiety_probability: float
    depression_probability: float
    severity: Dict[str, str]
    comorbidity: str
    rag_recommendations: List[LegacyRAGRecommendation] = Field(default_factory=list)
    query_used: str
    timestamp: str
    session_id: Optional[str] = None
    screen_time_insights: Optional[ScreenTimeInsights] = None
