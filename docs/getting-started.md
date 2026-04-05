# Getting started

## Prerequisites

- Python 3.10+ (3.11+ recommended for tooling compatibility)
- pip

Optional: Flutter SDK for the mobile app; Docker for containerized gateway.

## Install dependencies

From the **repository root**:

```bash
python -m pip install -r requirements.txt
```

Legacy API-only installs still work from `src/api` using `src/api/requirements.txt` (subset; root file is preferred for microservices + tests).

## Run the microservices gateway (recommended)

```bash
export PYTHONPATH=.
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
```

Windows (cmd):

```bat
set PYTHONPATH=.
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
```

- OpenAPI: `http://localhost:8000/docs`
- Health: `GET /health`

See [Microservices & gateway API](services/microservices.md) for the `POST /api/assess` contract.

## Run the legacy API (`src/api`)

```bash
cd src/api
python -m pip install -r requirements.txt
python main.py
```

Interactive client: `python test_api.py` (from `src/api`).

Details: [Legacy FastAPI](reference/legacy-api.md).

## Chroma / vector data

- Default gateway uses `data/vector_db_mini` and collection `clinical_rag_mini` unless overridden.
- Optional enriched index: [Ingestion & vector index](services/ingestion.md).

## Tests

From repository root:

```bash
python -m pytest tests -q
```

## Next steps

- [Architecture overview](architecture/overview.md)
- [Roadmap & team split](roadmap/upheal-rag-next-phase.md)
