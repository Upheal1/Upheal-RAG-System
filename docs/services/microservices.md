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
| `session_id` | string | Optional. Legacy/mobile session tracking (echoed back in response). |
| `locale` | string | Optional. Output locale for safety/auditor copy. Supported: `en`, `ar`. Default: `en`. |
| `raw_forms_json` | object or list | Optional wrapper for form payload. |
| `screen_time_minutes` | number | Total screen time in minutes; drives sigmoid `R_app` in `app_exposure_ratios`. |
| `answers` | object (string → int) | Optional. Question id → score (e.g. GAD-7 / PHQ-9 style `gad7_q1`, `phq9_q1`). Merged into `raw_forms_json` as `{"answers": ...}` when both are sent. |

**Supported `raw_forms_json` shapes**

1. **`{"answers": {"gad7_q1": 2, "phq9_q1": 1, ...}}`** — preferred.
2. **Flat answers dict** — if keys look like question ids (`gad` / `phq` in id), the whole dict is treated as answers.
3. **`risk_flags`** — e.g. `{"answers": {...}, "risk_flags": {"suicidal": true}}`. Suicidal flag adds `form_scores["suicidal"]` so the Clinical Auditor can escalate to RED.

**Strict validation (PHQ-9 / GAD-7)**

- If any `gad7_q*` / `phq9_q*` keys are present, the API requires a complete set:
  - **GAD-7:** `gad7_q1..gad7_q7`
  - **PHQ-9:** `phq9_q1..phq9_q9`
- Values must be integers in **0..3**.
- Invalid payloads return **422** with a structured `detail`.

**Response:** `AssessGatewayResponse` (includes all `FinalRoadmap` fields plus legacy/mobile fields).

Legacy/mobile fields included:

- `anxiety_probability`, `depression_probability`
- `severity` (`{"anxiety": "...", "depression": "..."}`), `comorbidity` (string `"true"`/`"false"`)
- `rag_recommendations[]` (legacy shape: `source`, `section`, `content`, `similarity`, `pages`)
- `query_used`, `timestamp`, `session_id`

**Example (Postman-ready)**

```json
{
  "user_id": "u_test",
  "session_id": "s_test",
  "locale": "en",
  "screen_time_minutes": 120,
  "raw_forms_json": {
    "answers": {
      "gad7_q1": 2,
      "gad7_q2": 2,
      "gad7_q3": 1,
      "gad7_q4": 1,
      "gad7_q5": 0,
      "gad7_q6": 2,
      "gad7_q7": 1,
      "phq9_q1": 1,
      "phq9_q2": 1,
      "phq9_q3": 0,
      "phq9_q4": 1,
      "phq9_q5": 0,
      "phq9_q6": 1,
      "phq9_q7": 0,
      "phq9_q8": 0,
      "phq9_q9": 0
    }
  }
}
```

## Assessment pipeline

- **Form scores:** GAD/PHQ totals normalized to 0–100 (max 21 / 27), blended with Bayesian output from [`src/api/assessment_engine.py`](../../src/api/assessment_engine.py) when answers are present.
- **Screen time:** `R_app = 1 / (1 + exp(-0.05 * (minutes - 60)))`.

## Knowledge base (Chroma)

- **Default:** `data/vector_db_mini`, collection `clinical_rag_mini` (legacy metadata).
- **Enriched index (optional):** see [Ingestion & vector index](ingestion.md). Set:

  - `UPHEAL_CHROMA_PATH` — path to the Chroma persistence directory  
  - `UPHEAL_CHROMA_COLLECTION` — collection name  

### `GET /knowledge_base/health`

Knowledge-base health per Phase 1 spec.

Response (`KnowledgeBaseHealthResponse`):

| Field | Type | Description |
|-------|------|-------------|
| `indexed_tasks` | int | Number of documents in the Chroma collection |
| `storage_status` | string | `healthy` (has docs), `degraded` (empty but reachable), or `unavailable` |
| `last_ingestion` | string (ISO-8601) or null | Timestamp of the last ingestion run, if known |

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
