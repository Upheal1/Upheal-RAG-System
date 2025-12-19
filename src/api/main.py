"""
UpHeal FastAPI Backend - Clinical RAG API
Connects Flutter mobile app to Python RAG system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from models import AssessmentRequest, AssessmentResponse, RAGRecommendation, HealthResponse
from rag_client import RAGClient
from assessment_engine import run_assessment

# Initialize FastAPI app
app = FastAPI(
    title="UpHeal Clinical RAG API",
    version="1.0.0",
    description="REST API for clinical assessment and RAG-based treatment recommendations"
)

# Enable CORS for Flutter app
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # In production, specify your app's domain
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Initialize RAG client (singleton)
print("Initializing RAG client...")
rag_client = RAGClient()
print("✓ RAG client ready")

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint - API info"""
    return {
        "name": "UpHeal Clinical RAG API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "assess": "/api/assess"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        rag_loaded=rag_client.is_loaded(),
        total_documents=rag_client.get_document_count()
    )

@app.post("/api/assess", response_model=AssessmentResponse, tags=["Assessment"])
def clinical_assessment(request: AssessmentRequest):
    """
    Run clinical assessment and get RAG recommendations
    
    - **answers**: Dictionary of question_id -> answer_value (0-3)
    - **user_id**: Firebase user ID
    - **session_id**: Optional session identifier
    """
    try:
        # 1. Run Bayesian assessment
        print(f"Running assessment for user: {request.user_id}")
        results = run_assessment(request.answers)
        
        # 2. Query RAG system
        print(f"Querying RAG with: {results['query']}")
        rag_results = rag_client.query(results['query'], top_k=5)
        
        # 3. Format response
        recommendations = [
            RAGRecommendation(**rec) for rec in rag_results
        ]
        
        response = AssessmentResponse(
            anxiety_probability=results['anxiety_probability'],
            depression_probability=results['depression_probability'],
            severity={
                "anxiety": results['anxiety_severity'],
                "depression": results['depression_severity']
            },
            comorbidity=results['comorbidity'],
            rag_recommendations=recommendations,
            query_used=results['query'],
            timestamp=datetime.now().isoformat()
        )
        
        print(f"✓ Assessment complete - Anxiety: {results['anxiety_probability']:.2f}, Depression: {results['depression_probability']:.2f}")
        return response
        
    except Exception as e:
        print(f"Error during assessment: {e}")
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print("Starting UpHeal Clinical RAG API Server")
    print("="*70)
    uvicorn.run(app, host="localhost", port=8000, reload=False)
