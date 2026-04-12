# Phase 1 — Knowledge Infrastructure

## Overview

Phase 1 establishes the **brain** of the UpHeal system: a metadata-enriched clinical knowledge base and strict API contracts so downstream agents can reason over atomic, labelled therapeutic units. Raw clinical corpora become agent-ready artefacts through ingestion, semantic chunking, formatter labelling, and hybrid vector storage with integrity guarantees.

## Architecture Diagram

```
  clinical_pdfs/          services/ingestion/
       │                         │
       │  pdf_utils.py           │
       ├────────────────────────►│  extract + denoise
       │                         │
       │                    semantic_chunker.py
       │                         │  sliding windows + 15% overlap
       │                         ▼
       │                    formatter_agent.py
       │                    (LLM labels per chunk)
       │                         │
       ▼                         ▼
  services/shared/         build_index / persist
  schemas.py ────────────────────┐
  logging.py                     │
  state.py                       ▼
                          knowledge_base/
                          chroma_adapter.py
                          (hybrid query + HNSW persist)
                                 │
                                 ▼
                          scripts/verify_integrity.py
                          GET /health (indexed_tasks, …)
```

## Detailed Specifications

### Section 1 — Shared Foundation & API Contracts

#### 1.1 `services/shared/schemas.py`

Define the following Pydantic v2 models. These are the canonical contracts for Phase 1 and all later phases.

**Model: `ClinicalTask`** (the atomic unit of knowledge)

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `UUID` | Persistent unique identifier for the task |
| `content` | `str` | Core therapeutic instruction or exercise text |
| `symptom_tags` | `List[str]` | E.g. `["anxiety", "insomnia", "dopamine-regulation"]` |
| `difficulty` | `int` (1–5) | Allows the Director Agent to scale roadmap difficulty |
| `xp_reward` | `int` | Calculated from task complexity |
| `source_reference` | `str` | E.g. `"Beck Institute - CBT Manual p.45"` |
| `metadata` | `dict` | JSONB blob: section headers, page numbers, formatting hints |
| `safety_risk` | `bool` | Flagged `True` if crisis/emergency keywords detected |
| `utility_score` | `float` | Global score updated by the Self-Refining loop (Phase 4) |

**Model: `UserContext`**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `UUID` | User identifier |
| `phq9_score` | `int` | Raw PHQ-9 integer (0–27) |
| `gad7_score` | `int` | Raw GAD-7 integer (0–21) |
| `screen_time_minutes` | `int` | Daily screen time from device |
| `r_app` | `float` | Computed sigmoid digital-strain ratio |
| `clinical_weights` | `dict` | Normalised 0.0–1.0 per symptom domain |
| `safety_status` | `str` | `"GREEN"` \| `"AMBER"` \| `"RED"` |

**Model: `RetrievalQuery`**

| Field | Type | Description |
|-------|------|-------------|
| `query_text` | `str` | Synthesised semantic search string |
| `symptom_keywords` | `List[str]` | Top-3 keywords by highest normalised score |
| `max_difficulty` | `int` | Upper difficulty bound for ChromaDB `$lte` filter |
| `boost_digital_detox` | `bool` | `True` when `r_app > 0.8` |

#### 1.2 Shared Utilities

**`services/shared/logging.py` — structured JSON logger**

Every log line MUST be structured JSON including at minimum: `timestamp`, `service`, `event`, `payload` (object). Use a single logger factory per service module so `service` reflects the package name (e.g. `ingestion.formatter_agent`).

**Tracing one PDF from ingestion to indexed chunk**

1. **Ingest start** — `event: "ingestion.pdf.start"`, `payload: { "source_path": "...", "sha256": "..." }`.
2. **Chunk emitted** — `event: "ingestion.chunk.created"`, `payload: { "chunk_index": n, "source_path": "...", "byte_span": [...] }`.
3. **Formatter** — `event: "ingestion.formatter.done"`, `payload: { "task_id": "...", "difficulty": 2, "xp_reward": 50 }`.
4. **Index write** — `event: "kb.chroma.upsert"`, `payload: { "collection": "...", "ids": ["..."] }`.

Correlate by `payload.source_path` and `payload.task_id` / Chroma `id` across stages.

**`services/shared/state.py` — pathing helper for clinical PDFs**

A `pathlib`-centric helper resolves repo-root-relative paths, validates that configured directories exist, and exposes iterators for “pending ingest” vs “archived” PDFs.

**Expected directory layout**

```
data/
├── clinical_pdfs/
│   ├── inbox/              # Drop new PDFs here for batch ingest
│   ├── processing/         # Optional: files currently being chunked
│   └── archive/            # Successfully indexed originals (optional copy)
├── rag_chunks/             # Intermediate JSON chunks (if used)
└── vector_db_mini_enriched/  # Chroma persistent path (example)
```

---

### Section 2 — The Ingestion Pipeline (`services/ingestion/`)

The **Building Factory**: raw PDFs enter; agentic-ready `ClinicalTask` metadata and vectors exit.

#### 2.1 `services/ingestion/pdf_utils.py` — PDF extraction and cleaning

- Extract text while preserving **headers**, **lists**, and **tables** (recommend `pdfplumber` or `pymupdf` / Fitz).
- **Noise filter** (heuristic rules):
  - Drop lines matching bibliography patterns (e.g. years in brackets, DOI URLs, “References” section after first occurrence).
  - Remove running **headers/footers** by detecting repeated short lines at fixed vertical bands across pages.
  - Strip **legal/disclaimer** blocks when keywords appear (`disclaimer`, `not a substitute for professional`, etc.).
  - Remove **index** sections (lines dominated by dot leaders and page numbers).
- Normalise Unicode, collapse excessive whitespace, preserve paragraph breaks for the chunker.

#### 2.2 `services/ingestion/semantic_chunker.py` — Semantic chunker

- **Sliding window** aligned to **sentence boundaries** and **paragraph themes**, not fixed character cuts.
- **15% overlap** between consecutive chunks so connectors (“In the next step…”) stay co-located with prior context.
- **New chunk boundary** when:
  - A hard paragraph break occurs AND the current buffer exceeds a minimum token/character budget, OR
  - A **topic shift** is detected via lightweight keyword / embedding cosine drop between adjacent sentences, OR
  - A maximum chunk size is reached (safety cap) at the nearest sentence end.

#### 2.3 `services/ingestion/formatter_agent.py` — The Formatter Agent

A specialised LLM agent (Gemini or GPT) runs **per chunk** before indexing. It outputs structured labels consumed by the index builder.

**Labelling rules**

| Condition detected in chunk | Action |
|-----------------------------|--------|
| Describes an exercise or practice | Assign high `xp_reward` (≥ 80) |
| Educational/theoretical content | Assign `difficulty` ≤ 2 |
| Keywords: "Crisis", "Suicide", "Emergency" | Set `safety_risk = True` |
| Describes a multi-step protocol | Raise `difficulty` by +1 |

**System prompt template** (fenced template; placeholders in ALL_CAPS):

```
You are the UpHeal Formatter Agent. You label CBT/clinical text chunks for a therapeutic app.
Output ONLY valid JSON matching the schema: task_id (omit if not assigned externally), symptom_tags (string array), difficulty (1-5 int), xp_reward (int), safety_risk (bool), source_reference (string), metadata (object with section, pages optional).

Rules:
- If the chunk is an exercise or practice, set xp_reward >= 80.
- If the chunk is educational/theoretical only, set difficulty <= 2.
- If you see crisis/suicide/emergency language, set safety_risk true.
- If the chunk describes a multi-step protocol, add +1 to difficulty (cap at 5).

Chunk text:
"""
CHUNK_TEXT_HERE
"""
```

> ⚠️ **Safety Note:** Formatter output must never be trusted as clinical advice; it only labels content for retrieval. Crisis content must flow to auditor/gateway policies in later phases.

---

### Section 3 — Knowledge Base Core (`services/knowledge_base/`)

#### 3.1 `services/knowledge_base/chroma_adapter.py` — ChromaDB hybrid adapter

- **Initialisation**: persistent client path + collection; prefer **HNSW**-backed configuration where Chroma exposes it for the deployment target.
- **Hybrid querying** (illustrative pseudocode):

```
where_filter = {"difficulty": {"$lte": retrieval_query.max_difficulty}}
where_doc = {"$contains": "panic attack"}   # or keyword from symptom_keywords
results = collection.query(
    query_embeddings=[embedding],
    n_results=k,
    where=where_filter,
    where_document=where_doc,
    include=["documents", "metadatas", "distances"],
)
```

- **Parallel indexing (factory run)**: use `concurrent.futures.ThreadPoolExecutor` to parallelise **embedding computation** and **batch upserts**. Chroma’s Python client is not always thread-safe for concurrent writes to the *same* collection; recommended pattern: **single writer thread** (or process) consuming a queue of precomputed embeddings, or **shard by batch** with one client per worker writing to disjoint ID ranges under documented Chroma version constraints. Document the chosen pattern in the implementation ADR.

#### 3.2 Health and integrity monitoring

- **`GET /health`** (knowledge-base service or gateway aggregate): returns JSON:

```json
{
  "indexed_tasks": 0,
  "storage_status": "OK",
  "last_ingestion": "2026-04-11T12:00:00Z"
}
```

- **`scripts/verify_integrity.py`**: scans Chroma metadata for mandatory fields (`xp_reward`, `difficulty`, `symptom_tags`). **Output**: Markdown or CSV **table** of violating `task_id` rows with missing field names.

---

## Technical Deliverables

- [ ] `services/shared/schemas.py` — updated with strict type-hinting for `ClinicalTask`, `UserContext`, `RetrievalQuery`.
- [ ] `services/shared/logging.py` — structured JSON logger implemented.
- [ ] `services/shared/state.py` — pathlib pathing helper implemented.
- [ ] `services/ingestion/pdf_utils.py` — PDF extraction and noise filter implemented.
- [ ] `services/ingestion/semantic_chunker.py` — sliding-window chunker with 15% overlap implemented.
- [ ] `services/ingestion/formatter_agent.py` — LLM Formatter Agent integrated with Gemini/GPT.
- [ ] `services/knowledge_base/chroma_adapter.py` — hybrid filtering and parallel indexing implemented.
- [ ] `scripts/verify_integrity.py` — consistency check script implemented.
- [ ] `scripts/migrate_initial_clinical_library.py` — migration script to ingest the initial clinical PDF library into the new schema.

## Success Metric

> **Precision retrieval**: A query for "Low difficulty anxiety exercises" must return tasks where `difficulty <= 2` AND `symptom_tags` includes `"anxiety"`, sorted by semantic similarity score descending.

## File Map

```
services/shared/schemas.py          # Pydantic v2 contracts: ClinicalTask, UserContext, RetrievalQuery
services/shared/logging.py          # JSON structured logging with correlation-friendly payload
services/shared/state.py            # pathlib helpers + clinical PDF directory layout
services/ingestion/pdf_utils.py     # Extract + denoise PDFs for chunking
services/ingestion/semantic_chunker.py  # Sentence/paragraph-aware chunks, 15% overlap
services/ingestion/formatter_agent.py     # LLM labelling agent (per-chunk JSON)
services/knowledge_base/chroma_adapter.py # Hybrid Chroma queries + batch/parallel ingest strategy
scripts/verify_integrity.py         # Mandatory-field scan over Chroma metadata
scripts/migrate_initial_clinical_library.py  # One-shot ingest of seed PDF library
```
