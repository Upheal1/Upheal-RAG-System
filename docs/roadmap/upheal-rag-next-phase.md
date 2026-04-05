# Upheal microservices: upcoming modifications plan

Shared roadmap for the team. Phase A/B items below are largely implemented; this document stays useful for context, verification, and Phase C / future work.

## Current baseline (what already works)

- Flow: [`services/gateway/main.py`](../../services/gateway/main.py) → `build_user_context` → `ChromaKnowledgeBase.retrieve_tasks` → `run_architect_pipeline` → `audit_roadmap` → `FinalRoadmap`.
- Chroma documents are built by [`src/rag/build_vector_store_mini.py`](../../src/rag/build_vector_store_mini.py) with **flat metadata only**: `source_file`, `char_count`, `page_numbers`, `header` (no `clinical_tags` / `difficulty` / `xp_reward` yet).
- Gateway API and KB paths: [Microservices & gateway API](../services/microservices.md).

```mermaid
flowchart LR
  Gateway[Gateway] --> Assessment[assessment_core]
  Assessment --> UserCtx[UserContext]
  UserCtx --> KB[chroma_adapter]
  KB --> Tasks[List_ClinicalTask]
  Tasks --> Architect[rerank_plus_audit]
  Architect --> Roadmap[FinalRoadmap]
```

## Phase A — Quick wins (no vector rebuild)

**A1. Lock the API contract** — Document `AssessRequest` in [`services/gateway/main.py`](../../services/gateway/main.py) and [Microservices & gateway API](../services/microservices.md).

**A2. Stronger assessment** — In [`services/assessment/core.py`](../../services/assessment/core.py): optionally reuse Bayesian scoring from [`src/api/assessment_engine.py`](../../src/api/assessment_engine.py) while keeping `UserContext.form_scores` as normalized ints.

**A3. Better retrieval query** — In [`services/knowledge_base/chroma_adapter.py`](../../services/knowledge_base/chroma_adapter.py): build `query_text` from assessment outputs.

**A4. Tests** — [`tests/`](../../tests) with `pytest` for sigmoid, normalization, `rerank_tasks`, `audit_roadmap`.

**A5. Run story** — Root [`requirements.txt`](../../requirements.txt) and `uvicorn services.gateway.main:app`. Legacy: [`src/api/requirements.txt`](../../src/api/requirements.txt).

## Phase B — RAG quality jump (requires rebuild or new collection)

**B1. Rich chunk metadata** — [`services/ingestion/build_index.py`](../../services/ingestion/build_index.py) + [`formatter_agent.py`](../../services/ingestion/formatter_agent.py).

**B2. Hybrid retrieval** — [`chroma_adapter.py`](../../services/knowledge_base/chroma_adapter.py) with Chroma `where` / `where_document` and [`schemas.py`](../../services/shared/schemas.py) if you reintroduce `RetrievalQuery`.

**B3. True `ClinicalTask` shaping** — Map stored metadata into task fields (not header-only inference).

**B4. Rebuild + verify** — See [Ingestion & vector index](../services/ingestion.md); smoke test `GET /health`, `POST /api/assess`.

## Phase C — Optional cleanup

- Remove or fold health-only routers under `services/*/router.py`.

## Suggested implementation order

1. Phase A — no data migration.
2. Phase B — one-time index rebuild when metadata schema is stable.
3. Phase C — optional slimmer tree.

## Decision before Phase B

- **Overwrite** `data/vector_db_mini` vs **parallel** store. Current default: parallel `vector_db_mini_enriched` / `clinical_rag_mini_enriched` — [Ingestion & vector index](../services/ingestion.md).

---

## Suggested two-person split (next enhancements)

### Person A — Clinical API and assessment

| Task | Why |
|------|-----|
| Align `POST /api/assess` with Flutter/legacy [`src/api/main.py`](../../src/api/main.py) if the app expects the old JSON | Avoid breaking mobile clients |
| Harden [`services/assessment/core.py`](../../services/assessment/core.py): schemas, missing items, PHQ/GAD validation | Clinical correctness |
| Extend [`services/architect/auditor.py`](../../services/architect/auditor.py): keywords, clinician copy, locale | Safety and tone |
| Expand [`tests/test_assessment.py`](../../tests/test_assessment.py) | Regression safety |

### Person B — RAG, ingestion, and index

| Task | Why |
|------|-----|
| Run/document enriched index; standardize `UPHEAL_*` in docs / `.env.example` | Reproducible KB |
| Improve [`formatter_agent.py`](../../services/ingestion/formatter_agent.py) for taxonomy-aligned tags | Retrieval + reranking |
| Tune [`chroma_adapter.py`](../../services/knowledge_base/chroma_adapter.py): `where`, `n_fetch`, `where_document` | Hybrid quality |
| Add tests that mock Chroma or use a fixture DB | Safer KB changes |

### Either person — Phase C (optional)

| Task | Why |
|------|-----|
| Remove or merge health-only `services/*/router.py` | Simpler ops |

### Sync points (both)

- Agree on **`ClinicalTask` / `UserContext` / `FinalRoadmap`** in [`services/shared/schemas.py`](../../services/shared/schemas.py).
- Align on Chroma path/collection + one shared `POST /api/assess` example (document in [Microservices & gateway API](../services/microservices.md)).
