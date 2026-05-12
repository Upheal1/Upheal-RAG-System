# 🚀 Quick Start - UpHeal RAG for Partners

## One-Command Setup

```bash
# 1. Clone & Enter
git clone <repo-url> && cd Upheal-RAG-System

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run server (Windows)
set PYTHONPATH=. && python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000

# 3. Run server (Mac/Linux)
export PYTHONPATH=. && python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
```

## Test in Browser

- Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

## Test in Postman

1. Import: `UpHeal-RAG-Postman-Collection.json`
2. Set variable `baseUrl` = `http://localhost:8000`
3. Send requests!

## Key Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | No | Check server status |
| `/api/assess` | POST | No | Submit assessment |
| `/api/roadmap` | POST | No | Generate roadmap |
| `/knowledge_base/query` | POST | No | Query RAG directly |
| `/api/chat` | POST | Yes | Chat with AI |

## Sample Request (Assessment)

```json
POST http://localhost:8000/api/assess
Content-Type: application/json

{
  "user_id": "test_user",
  "answers": {
    "gad7_q1": 2,
    "gad7_q2": 3,
    "phq9_q1": 1,
    "phq9_q2": 2
  }
}
```

## Sample Response

```json
{
  "anxiety_probability": 0.65,
  "depression_probability": 0.35,
  "severity": {
    "anxiety": "Moderate",
    "depression": "Mild"
  },
  "overview_paragraph": "Based on your assessment...",
  "suggested_tasks": [...],
  "safety_status": "GREEN"
}
```

## Prerequisites Check

Before starting, ensure you have:
- Python 3.10+ installed: `python --version`
- The `data/vector_db_mini/` directory exists (contains the RAG knowledge base)

## Need Help?

See `PARTNER_SETUP.md` for detailed instructions.
