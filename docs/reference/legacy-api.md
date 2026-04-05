# Legacy API backend (`src/api`)

FastAPI server that connects the original Python RAG stack to the Flutter app.

> **Note:** The recommended path for new work is the microservices gateway under `services/` — see [Microservices & gateway API](../services/microservices.md).

## Setup

```bash
cd src/api
python -m pip install -r requirements.txt
python main.py
```

Server: `http://localhost:8000`

## Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application |
| `models.py` | Pydantic request/response schemas |
| `assessment_engine.py` | Bayesian assessment logic |
| `rag_client.py` | Chroma / embedding wrapper |
| `test_api.py` | Interactive terminal test |

## Endpoints

- `GET /` — API info
- `GET /health` — Health check
- `POST /api/assess` — Clinical assessment (legacy response shape)

## Testing

```bash
cd src/api
python test_api.py
```

Swagger UI: `http://localhost:8000/docs`

## Production notes

- Restrict CORS (avoid `*` in production).
- Use environment variables for secrets and paths.
- Enable HTTPS and rate limiting where appropriate.
