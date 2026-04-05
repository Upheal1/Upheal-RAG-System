# Upheal microservices (`services/`)

Canonical documentation for this workspace lives under **[`docs/`](../docs/README.md)**.

- **Gateway, API contract, Chroma:** [docs/services/microservices.md](../docs/services/microservices.md)
- **Ingestion & enriched index:** [docs/services/ingestion.md](../docs/services/ingestion.md)
- **Roadmap & team split:** [docs/roadmap/upheal-rag-next-phase.md](../docs/roadmap/upheal-rag-next-phase.md)

Quick run (from repo root):

```bash
export PYTHONPATH=.
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
```
