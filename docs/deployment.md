# Deployment

Docker scaffolding lives under [`deployments/`](../deployments/).

## Current behavior

The gateway runs in a **single container** with in-process orchestration. Domain boundaries are preserved as Python packages under `services/`.

Deployed to **Render** (free tier, 512MB RAM) at `https://upheal-rag.onrender.com`.

## Files

- [`deployments/Dockerfile`](../deployments/Dockerfile) — image build (installs deps, sets `PYTHONPATH`, runs uvicorn on `services.gateway.main:app`)
- [`deployments/docker-compose.yml`](../deployments/docker-compose.yml) — example `gateway` service mapping port 8000
- [`deployments/render.yaml`](../deployments/render.yaml) — Render service config
- [`deployments/upheal-rag.env`](../deployments/upheal-rag.env) — reference for all Render env vars
- [`.dockerignore`](../.dockerignore) — reduces build context from 430MB+ to ~136MB

## Build and run (local Docker)

From repository root:

```bash
docker compose -f deployments/docker-compose.yml up --build
```

Or build the Dockerfile directly:

```bash
docker build -f deployments/Dockerfile -t upheal-rag .
docker run -p 8000:8000 --env-file deployments/upheal-rag.env upheal-rag
```

## Render deployment

The service auto-deploys from the `main` branch via `render.yaml`.

### Key environment variables

| Variable | Value | Notes |
|----------|-------|-------|
| `UPHEAL_CHROMA_PATH` | `./data/vector_db_mini` | Relative path (works on Render + Docker + local) |
| `UPHEAL_CHROMA_COLLECTION` | `clinical_rag_mini` | Matches data in vector_db_mini |
| `UPHEAL_EMBEDDING_MODEL` | `all-mpnet-base-v2` | Clinical accuracy over speed |
| `SUPABASE_JWT_SECRET` | (UUID key) | JWT validation |
| `UPHEAL_SUPABASE_URL` | `https://gcxxmjptbyvlabqzcprv.supabase.co` | |
| `UPHEAL_SUPABASE_KEY` | (service role key) | |

### Path resolution

The ChromaDB path is resolved by `resolve_chroma_path()` in `services/shared/pathing.py`. It tries multiple paths in order:

1. `UPHEAL_CHROMA_PATH` env var
2. `./data/vector_db_mini` (relative to cwd)
3. `/opt/render/project/src/data/vector_db_mini` (Render)
4. `/app/data/vector_db_mini` (Docker WORKDIR)
5. `repo_root()` fallback (local dev)

### Working directory notes

| Environment | Working directory | Effective data path |
|-------------|-------------------|---------------------|
| Render | `/opt/render/project/src/` | `./data/vector_db_mini` resolves correctly |
| Docker (Dockerfile) | `/app/` | `./data/vector_db_mini` or `/app/data/vector_db_mini` |
| Local dev | repo root | `./data/vector_db_mini` resolves correctly |

### Memory constraints

Render free tier = 512MB RAM. The embedding model (`all-mpnet-base-v2`, ~420MB) is **lazy-loaded** — not loaded at import time or during health checks. It only loads when an actual query is made via `ChromaKnowledgeBase._ensure_loaded()`.

Health checks are **lightweight** (filesystem-based, no model loading) and support `HEAD` requests for Render health checker compatibility.

## Configuration

- Chroma path/collection: set `UPHEAL_CHROMA_PATH` and `UPHEAL_CHROMA_COLLECTION` in compose environment if using the enriched index (see [Ingestion & vector index](services/ingestion.md)).

## Local run without Docker

See [Getting started](getting-started.md).

## Troubleshooting

### Health check returns `knowledge_base_healthy: false`

1. Check `/debug/paths` (if available) to see actual CWD and path resolution
2. Verify `UPHEAL_CHROMA_PATH` is set to `./data/vector_db_mini` (relative)
3. Ensure vector DB data is in git (only tracked files make it into the Docker build)

### OOM crash on Render

- The model is lazy-loaded; health checks don't load it
- If OOM still occurs, reduce uvicorn workers to 1 (`--workers 1`)

### 502 Bad Gateway

- Ensure all health endpoints support `HEAD` method (Render sends HEAD requests)