from pydantic import BaseModel
from typing import Dict, List, Optional

class AssessmentRequest(BaseModel):
    """Request model for clinical assessment"""
    answers: Dict[str, int]  # e.g., {"gad7_q1": 2, "phq9_q1": 3}
    user_id: str
    session_id: Optional[str] = None

class RAGRecommendation(BaseModel):
    """Single recommendation from RAG system"""
    source: str
    section: str
    content: str
    similarity: float
    pages: str

class AssessmentResponse(BaseModel):
    """Response model with assessment results and RAG recommendations"""
    anxiety_probability: float
    depression_probability: float
    severity: Dict[str, str]
    comorbidity: bool
    rag_recommendations: List[RAGRecommendation]
    query_used: str
    timestamp: str

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    rag_loaded: bool
    total_documents: int
