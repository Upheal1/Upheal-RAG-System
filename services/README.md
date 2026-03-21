## Upheal microservices workspace

This workspace was created from the `upheal-microservices_cef92291.plan.md` plan.

Current state:
- `services/shared/` contains Pydantic contracts and common utilities.
- `services/assessment/` implements `build_user_context()` with the `R_app` (screen time) math.
- `services/knowledge_base/`, `services/ingestion/`, and `services/architect/` contain import-safe scaffolding.
- `services/gateway/` exposes a FastAPI entrypoint with:
  - `GET /health`
  - `POST /api/assess`

Next iteration (per plan): port real form logic, implement hybrid search filtering metadata,
and connect architect reranking to the formatted chunk metadata pipeline.

