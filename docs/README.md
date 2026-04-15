# Upheal-RAG-System documentation

Canonical documentation for the project. Package-level folders (`services/`, `src/`) keep short README stubs that link here.

## Contents

| Doc | Description |
|-----|-------------|
| [Getting started](getting-started.md) | Install, run legacy API vs microservices gateway, tests |
| [Architecture overview](architecture/overview.md) | Repository layout, data flow, stack |
| [Microservices & gateway API](services/microservices.md) | `services/` layout, `POST /api/assess`, Chroma env vars |
| [Ingestion & vector index](services/ingestion.md) | Enriched Chroma build, `UPHEAL_*` variables |
| [Roadmap & team split](roadmap/upheal-rag-next-phase.md) | Phased plan and suggested two-person work split |
| [Deployment](deployment.md) | Docker scaffolding under `deployments/` |
| **Implementation Tracking** | |
| [Implementation Status](./implementation/README.md) | Task board, sprint timeline, progress |
| [Hozaifa Changelog](./implementation/hozaifa-changelog.md) | Hozaifa's implementation history |
| [Yahya Changelog](./implementation/yahya-changelog.md) | Yahya's implementation history |
| [Quick Reference](./implementation/quick-reference.md) | Common patterns and workflows |
| **Reference (legacy `src/`)** | |
| [Legacy FastAPI (`src/api`)](reference/legacy-api.md) | Original monolith server |
| [RAG scripts (`src/rag`)](reference/rag-module.md) | Chunking, vector build, query scripts |
| [Clinical forms (`src/clinical_forms`)](reference/clinical-forms.md) | Intake engine and form JSON |

## Quick links

- Repository root overview: [../README.md](../README.md)
- Python dependencies (gateway + tests): [../requirements.txt](../requirements.txt)
