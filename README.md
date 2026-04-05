# UpHeal - Mental Health Clinical Assessment Platform

AI-powered clinical assessment system combining Bayesian inference with RAG (Retrieval-Augmented Generation) for evidence-based treatment recommendations.

**Documentation hub:** [docs/README.md](docs/README.md) (getting started, architecture, microservices API, ingestion, roadmap, deployment, legacy `src/` reference).

## 🏗️ Project Structure

```
UpHeal/
├── docs/                     # Canonical documentation (start here)
├── services/                 # Microservices-style gateway + domains (recommended API)
├── src/
│   ├── clinical_forms/       # Assessment form logic (Bayesian inference)
│   ├── rag/                  # RAG scripts (vector build, query)
│   ├── api/                  # Legacy FastAPI monolith
│   └── integration/          # System integration scripts
├── tests/                    # Pytest (services)
├── data/
│   ├── vector_db_mini/       # ChromaDB vector store
│   ├── books/                # Source PDFs
│   └── rag_chunks/           # Preprocessed semantic chunks
└── my_app/                   # Flutter mobile application (if present)
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- pip (Python package manager)
- Flutter SDK (for mobile app)

### 2. Install Dependencies

```bash
# From repository root (gateway + tests)
python -m pip install -r requirements.txt
```

Legacy monolith only: `cd src/api` and `python -m pip install -r requirements.txt`.

### 3. Run the API Server

**Recommended (microservices gateway):** from repo root, `export PYTHONPATH=.` then `python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000`. See [docs/getting-started.md](docs/getting-started.md).

**Legacy:** `cd src/api` and `python main.py`.

Server: `http://localhost:8000`

### 4. Test the System

```bash
# Interactive test (simulates real user)
python test_api.py
```

## 📚 API Documentation

Once the server is running, visit:
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **API Info**: http://localhost:8000

### Endpoints

#### `GET /health`
Check if API and RAG system are loaded

**Response:**
```json
{
  "status": "ok",
  "rag_loaded": true,
  "total_documents": 3255
}
```

#### `POST /api/assess`
Submit assessment and get RAG recommendations

**Request:**
```json
{
  "answers": {
    "gad7_q1": 2,
    "phq9_q1": 1
  },
  "user_id": "user_123"
}
```

**Response:**
```json
{
  "anxiety_probability": 0.75,
  "depression_probability": 0.35,
  "severity": {
    "anxiety": "Moderate",
    "depression": "Low"
  },
  "rag_recommendations": [...]
}
```

## 🧠 How It Works

1. **Assessment**: User answers GAD-7 (anxiety) and PHQ-9 (depression) questionnaires
2. **Bayesian Analysis**: Calculates probabilities using independent Bayesian updates
3. **Query Generation**: Creates natural language query based on severity
4. **RAG Retrieval**: Searches 3,255 DSM-5-TR chunks for relevant recommendations
5. **Response**: Returns probabilities + top 5 evidence-based recommendations

## 🔬 Technology Stack

- **Backend**: FastAPI (Python)
- **Vector Database**: ChromaDB
- **Embeddings**: SentenceTransformers (all-mpnet-base-v2)
- **Mobile App**: Flutter
- **Database**: Firebase (Firestore)

## 📱 Mobile App Integration

The Flutter app calls the API:

```dart
final response = await http.post(
  Uri.parse('http://YOUR_SERVER:8000/api/assess'),
  body: jsonEncode({'answers': answers, 'user_id': uid}),
);
```

## 🗂️ Data

- **Source**: DSM-5-TR (Diagnostic and Statistical Manual of Mental Disorders)
- **Chunks**: 3,255 semantic chunks
- **Embedding Model**: all-mpnet-base-v2 (768 dimensions)

## 🔐 Security Notes

- Add API keys to `.env` file (not tracked by git)
- Enable CORS only for production domains
- Use Firebase authentication for user management

## 👥 Team

- **Project Type**: Graduation Project
- **Purpose**: Clinical Psychology AI Assistant

## 📄 License

See LICENSE file

---

For detailed setup and architecture, see [docs/getting-started.md](docs/getting-started.md).
