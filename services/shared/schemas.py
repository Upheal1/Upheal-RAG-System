from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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


class RetrievalQuery(BaseModel):
    """
    Query specification for knowledge base retrieval.
    Used by chroma_adapter.retrieve_tasks() to apply semantic query,
    symptom filters, difficulty ceiling, and optional digital detox boost.
    """

    query_text: str
    symptom_keywords: List[str] = Field(default_factory=list)
    max_difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    boost_digital_detox: bool = False


class UserContext(BaseModel):
    user_id: str
    timestamp: str
    form_scores: Dict[str, int] = Field(default_factory=dict)
    app_exposure_ratios: Dict[str, float] = Field(default_factory=dict)
    user_stats: Dict[str, int] = Field(default_factory=dict)


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
