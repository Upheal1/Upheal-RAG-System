# Microservices workspace & gateway API

## Run the gateway

From the **repository root** (set `PYTHONPATH` so `services` imports resolve):

```bash
python -m pip install -r requirements.txt
export PYTHONPATH=.
python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
```

Windows (cmd): `set PYTHONPATH=.`

## API contract: `POST /api/assess`

Request body (`AssessRequest`):

| Field | Type | Description |
|--------|------|-------------|
| `user_id` | string | Required. Stable user identifier. |
| `raw_forms_json` | object or list | Optional wrapper for form payload. |
| `screen_time_minutes` | number | Total screen time in minutes; drives sigmoid `R_app` in `app_exposure_ratios`. |
| `answers` | object (string → int) | Optional. Question id → score (e.g. GAD-7 / PHQ-9 style `gad7_q1`, `phq9_q1`). Merged into `raw_forms_json` as `{"answers": ...}` when both are sent. |

**Supported `raw_forms_json` shapes**

1. **`{"answers": {"gad7_q1": 2, "phq9_q1": 1, ...}}`** — preferred.
2. **Flat answers dict** — if keys look like question ids (`gad` / `phq` in id), the whole dict is treated as answers.
3. **`risk_flags`** — e.g. `{"answers": {...}, "risk_flags": {"suicidal": true}}`. Suicidal flag adds `form_scores["suicidal"]` so the Clinical Auditor can escalate to RED.

**Response:** `FinalRoadmap` (`overview_paragraph`, `suggested_tasks`, `safety_status`, `next_checkup_days`).

## Assessment pipeline

- **Form scores:** GAD/PHQ totals normalized to 0–100 (max 21 / 27), blended with Bayesian output from [`src/api/assessment_engine.py`](../../src/api/assessment_engine.py) when answers are present.
- **Screen time:** `R_app = 1 / (1 + exp(-0.05 * (minutes - 60)))`.

## Knowledge base (Chroma)

- **Default:** `data/vector_db_mini`, collection `clinical_rag_mini` (legacy metadata).
- **Enriched index (optional):** see [Ingestion & vector index](ingestion.md). Set:

  - `UPHEAL_CHROMA_PATH` — path to the Chroma persistence directory  
  - `UPHEAL_CHROMA_COLLECTION` — collection name  

## Module map

| Path | Role |
|------|------|
| `services/shared/` | Pydantic schemas and helpers |
| `services/assessment/` | `build_user_context`, `build_retrieval_query_text` |
| `services/knowledge_base/` | Chroma retrieval + optional metadata filters |
| `services/architect/` | Rerank + `audit_roadmap` |
| `services/gateway/` | FastAPI entrypoint |
| `services/ingestion/` | Formatter + `build_index` |

## Roadmap

Team plan and two-person task split: [../roadmap/upheal-rag-next-phase.md](../roadmap/upheal-rag-next-phase.md).
