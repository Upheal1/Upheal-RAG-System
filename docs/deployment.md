# Deployment

Docker scaffolding lives under [`deployments/`](../deployments/).

## Current behavior

The gateway runs in a **single container** with in-process orchestration. Domain boundaries are preserved as Python packages under `services/`.

## Files

- [`deployments/Dockerfile`](../deployments/Dockerfile) — image build (installs deps, sets `PYTHONPATH`, runs uvicorn on `services.gateway.main:app`)
- [`deployments/docker-compose.yml`](../deployments/docker-compose.yml) — example `gateway` service mapping port 8000

## Build and run (example)

From repository root:

```bash
docker compose -f deployments/docker-compose.yml up --build
```

Adjust context paths in `docker-compose.yml` if your layout differs.

## Configuration

- Chroma path/collection: set `UPHEAL_CHROMA_PATH` and `UPHEAL_CHROMA_COLLECTION` in compose environment if using the enriched index (see [Ingestion & vector index](services/ingestion.md)).

## Local run without Docker

See [Getting started](getting-started.md).
