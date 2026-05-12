# Partner Setup Guide - UpHeal RAG System

This guide will help you set up and run the UpHeal RAG system locally for testing with Postman.

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Git** (to pull the repository)
- **Postman** (download from https://www.postman.com/downloads/)
- **Optional**: Docker (for easier setup)

---

## Method 1: Direct Python Setup (Recommended for Development)

### Step 1: Clone the Repository

```bash
# Open your terminal/command prompt and navigate to where you want the project
cd C:\Users\YourUsername\Projects  # Windows example
cd ~/Projects                      # Mac/Linux example

# Clone the repository
git clone <your-repo-url>
cd Upheal-RAG-System
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# From the repository root
python -m pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- Uvicorn (ASGI server)
- ChromaDB (vector database)
- Sentence Transformers (for embeddings)
- Pytest (for testing)

### Step 4: Set Up Environment Variables

Create a `.env` file in the root directory:

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

For basic local testing without authentication, the defaults should work. The system has development mode that allows JWT validation without a secret.

### Step 5: Run the Server

```bash
# Windows Command Prompt:
set PYTHONPATH=.
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000 --reload

# Windows PowerShell:
$env:PYTHONPATH="."
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000 --reload

# Mac/Linux:
export PYTHONPATH=.
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start at: **http://localhost:8000**

You should see output like:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## Method 2: Docker Setup (Easier, No Python Install Needed)

If you have Docker Desktop installed:

```bash
# From the repository root
docker compose -f deployments/docker-compose.yml up --build
```

This will:
- Start the gateway API on port 8000
- Start ChromaDB on port 8001
- Set up all services automatically

---

## Verification - Test the Server

Open your browser and visit:
- **Health Check**: http://localhost:8000/health
- **API Docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc

The health endpoint should return something like:
```json
{
  "status": "ok",
  "knowledge_base_healthy": true,
  "knowledge_base_documents": 3255
}
```

---

## Postman Setup

### Option A: Import the Collection (Easiest)

1. Open Postman
2. Click **Import** (top left)
3. Select **File** > **Upload Files**
4. Choose the `UpHeal-RAG-Postman-Collection.json` file (included in this repo)
5. The collection will be imported with all endpoints pre-configured

### Option B: Manual Setup

1. **Create a New Collection** called "UpHeal RAG API"
2. Set the base URL variable:
   - Click the collection name
   - Go to **Variables** tab
   - Add variable: `baseUrl` = `http://localhost:8000`

---

## API Endpoints Reference

### 1. Health Check (No Auth Required)
```
GET http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "knowledge_base_healthy": true,
  "knowledge_base_documents": 3255
}
```

---

### 2. Assessment (No Auth Required for Testing)
```
POST http://localhost:8000/api/assess
Content-Type: application/json
```

**Request Body (Minimal):**
```json
{
  "user_id": "test_user_123",
  "answers": {
    "gad7_q1": 2,
    "gad7_q2": 1,
    "gad7_q3": 2,
    "phq9_q1": 1,
    "phq9_q2": 0,
    "phq9_q3": 1
  }
}
```

**Full Request Body:**
```json
{
  "user_id": "test_user_123",
  "session_id": "session_456",
  "locale": "en",
  "answers": {
    "gad7_q1": 2,
    "gad7_q2": 3,
    "gad7_q3": 2,
    "gad7_q4": 1,
    "gad7_q5": 2,
    "gad7_q6": 1,
    "gad7_q7": 2,
    "phq9_q1": 1,
    "phq9_q2": 2,
    "phq9_q3": 1,
    "phq9_q4": 0,
    "phq9_q5": 1,
    "phq9_q6": 2,
    "phq9_q7": 1,
    "phq9_q8": 0,
    "phq9_q9": 0
  },
  "screen_time_minutes": 180,
  "screenTimeData": {
    "totalMinutes": 180,
    "socialMinutes": 120,
    "productivityMinutes": 60,
    "dailyUsage": [
      {"packageName": "com.instagram.android", "usageTime": 90, "category": "social"},
      {"packageName": "com.whatsapp", "usageTime": 30, "category": "social"},
      {"packageName": "com.microsoft.office.word", "usageTime": 60, "category": "productivity"}
    ]
  }
}
```

**Response:**
```json
{
  "user_id": "test_user_123",
  "anxiety_probability": 0.65,
  "depression_probability": 0.35,
  "severity": {
    "anxiety": "Moderate",
    "depression": "Mild"
  },
  "comorbidity": "none",
  "overview_paragraph": "Based on your assessment...",
  "suggested_tasks": [
    {
      "task_id": "task_1",
      "content": "Practice deep breathing exercises",
      "symptom_tags": ["anxiety", "stress"],
      "difficulty": 1,
      "xp_reward": 10,
      "safety_risk": false,
      "source_reference": "DSM-5-TR"
    }
  ],
  "safety_status": "GREEN",
  "next_checkup_days": 14,
  "rag_recommendations": [...],
  "query_used": "moderate anxiety mild depression recommendations",
  "timestamp": "2025-01-15T10:30:00Z",
  "session_id": "session_456"
}
```

---

### 3. Generate Roadmap (No Auth Required)
```
POST http://localhost:8000/api/roadmap
Content-Type: application/json
```

**Request Body:**
```json
{
  "user_id": "test_user_123",
  "answers": {
    "gad7_q1": 2,
    "gad7_q2": 3,
    "phq9_q1": 1,
    "phq9_q2": 2
  },
  "top_n": 5
}
```

**Response:** Similar to assessment but cleaner format focused on the roadmap.

---

### 4. Chat (Requires Authentication)
```
POST http://localhost:8000/api/chat
Content-Type: application/json
Authorization: Bearer <your-jwt-token>
```

**Request Body:**
```json
{
  "message": "I'm feeling anxious about my upcoming exam",
  "session_id": null,
  "roadmap_id": null
}
```

**Note**: For testing without real authentication, you can use a mock JWT. The system has development mode that accepts tokens without verification.

**Test Token:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwicm9sZSI6ImF1dGhlbnRpY2F0ZWQifQ.test
```

---

### 5. Get Chat History (Requires Auth)
```
GET http://localhost:8000/api/chat/{session_id}/history
Authorization: Bearer <your-jwt-token>
```

---

### 6. Get Roadmap (Requires Auth)
```
GET http://localhost:8000/api/roadmap/{user_id}
Authorization: Bearer <your-jwt-token>
```

---

### 7. Knowledge Base Query (No Auth)
```
POST http://localhost:8000/knowledge_base/query
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "anxiety treatment techniques",
  "top_k": 5
}
```

---

## Troubleshooting

### Issue: "Module not found" errors
**Solution**: Make sure you set `PYTHONPATH=.`

### Issue: ChromaDB not found
**Solution**: The vector database should be in `data/vector_db_mini/`. If missing, ask the repo owner for the data files or run the ingestion scripts.

### Issue: Port 8000 already in use
**Solution**: Change the port:
```bash
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8001
```

### Issue: Authentication errors on protected endpoints
**Solution**: 
- Use the test JWT token provided above
- Or set `SUPABASE_JWT_SECRET` in your `.env` file
- Or modify the endpoint to skip auth (development only)

---

## Quick Test Commands (cURL)

If you prefer command line over Postman:

```bash
# Health check
curl http://localhost:8000/health

# Assessment
curl -X POST http://localhost:8000/api/assess \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test123", "answers": {"gad7_q1": 2, "phq9_q1": 1}}'

# Roadmap
curl -X POST http://localhost:8000/api/roadmap \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test123", "answers": {"gad7_q1": 2}}'
```

---

## Next Steps

1. **Explore the API**: Visit http://localhost:8000/docs for interactive API documentation
2. **Run Tests**: `python -m pytest tests/ -q`
3. **Customize**: Modify the request bodies to test different scenarios

---

## Support

If you encounter issues:
1. Check the logs in the terminal where the server is running
2. Verify all files are present (especially in `data/vector_db_mini/`)
3. Ensure Python version is 3.10 or higher
4. Check that all dependencies installed correctly: `pip list`
