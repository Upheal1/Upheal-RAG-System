# Approach A — Foundation-First

## Section 1 — Overview

**Name:** Foundation-First  
**Metaphor:** “Build the factory floor before hiring the workers.”  
**Core principle:** Hozaifa completes the data layer (Phase 1 + Supabase migrations where listed) before Yahya depends on a real `services/knowledge_base/chroma_adapter.py`. Yahya uses Week 1 for API scaffolding and unit-testable agent logic with hardcoded `ClinicalTask` fixtures. Integration is a planned handoff after **A-HOZ-06**, not continuous renegotiation.

**When to choose this approach**

- The pair is new or communication overhead is high.  
- Clinical data correctness outweighs speed to demo.  
- The Chroma hybrid adapter design is still evolving.

> 💡 **Approach Advantage:** Hozaifa’s layer is testable before Yahya binds to it, so failures localize to one layer—no “mock vs real” ambiguity during the first integration.

> 🔴 **Approach Trade-off:** Yahya cannot run the full Profiler → Architect → Gamifier → Auditor chain on real vectors until Week 2; Week 1 is scaffolding, fixtures, and pure logic tests only.

---

## Section 2 — Role definitions in this approach

**Hozaifa — “The Factory Builder”**  
Owns Phase 1 end-to-end: `services/shared/schemas.py`, ingestion (`services/ingestion/*`), hybrid `services/knowledge_base/chroma_adapter.py`, `scripts/verify_integrity.py`, migration script, and `GET /health`. **A-HOZ-06** is the merge gate that unlocks Yahya’s real adapter calls.

**Yahya — “The Blueprinter”**  
Week 1: `services/gateway/main.py` skeleton, `services/assessment/core.py` (sigmoid \(R_{app}\), `UserContext`, `RetrievalQuery` per roadmap), and `tests/fixtures/clinical_tasks.py`. After **A-HOZ-06**, replaces fixture injection with the real knowledge base.

---

## Section 3 — Approach A phase mapping

### Phase 1 — Knowledge Infrastructure (Hozaifa leads, Yahya scaffolds)

In Approach A, Phase 1 implementation on the **real index** is Hozaifa’s lane until **A-HOZ-06** lands. Yahya does not call `chroma_adapter` for real retrieval until that gate is green, avoiding churn from unstable embeddings or metadata shapes.

### [A-HOZ-01] Define Pydantic schemas (`ClinicalTask`, `UserContext`, `RetrievalQuery`)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 1 |
| File | `services/shared/schemas.py` |
| Complexity | M |
| Depends On | None |
| Blocks | A-HOZ-02, A-HOZ-03, A-HOZ-04, A-HOZ-05, A-HOZ-06, A-YAH-01, A-YAH-02 |
| Status | 🔲 Not Started |

**What & Why:** Locks the shared contract for the whole roadmap: `ClinicalTask`, `UserContext`, and `RetrievalQuery` as defined in Phase 1. Every downstream file imports these types; doing this first prevents parallel rework.

**Acceptance Criteria:**

- [ ] All fields from Phase 1 tables exist with Pydantic v2 types (`UUID`, `List[str]`, etc.).
- [ ] `ClinicalTask` includes `safety_risk` and `utility_score` for Phases 2–4.
- [ ] CI runs `mypy` or import checks on `services/shared/schemas.py` without errors.

**Approach-Specific Note:** In Approach B this work ships on Day 1 **together** with the mock adapter as **B-HOZ-01**, not as a standalone merge before any consumer exists.

> ⚠️ **Integration Risk:** Any post-merge schema edit forces Yahya and Hozaifa to re-sync; treat schema PRs as dual-reviewed.

---

### [A-HOZ-02] Structured JSON logger

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 1 |
| File | `services/shared/logging.py` |
| Complexity | S |
| Depends On | A-HOZ-01 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Implements JSON lines with `timestamp`, `service`, `event`, `payload` so PDF→chunk→index traces are correlatable, per Phase 1 logging spec.

**Acceptance Criteria:**

- [ ] Each log entry is valid JSON with the four required keys.
- [ ] Ingestion events (`ingestion.pdf.start`, `ingestion.chunk.created`, `ingestion.formatter.done`, `kb.chroma.upsert`) can be traced by `source_path` / `task_id`.
- [ ] Documented usage example in module docstring.

**Approach-Specific Note:** Same implementation burden as Approach B; Approach A just sequences it strictly after schemas without mock pressure.

---

### [A-HOZ-03] PDF extraction and noise filter

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 2 |
| File | `services/ingestion/pdf_utils.py` |
| Complexity | M |
| Depends On | A-HOZ-02 |
| Blocks | A-HOZ-04 |
| Status | 🔲 Not Started |

**What & Why:** Extracts text preserving structure and applies bibliography/header/footer/disclaimer heuristics from Phase 1 so the chunker receives clean clinical prose.

**Acceptance Criteria:**

- [ ] At least one of `pdfplumber` or `pymupdf` documented as the extractor.
- [ ] Sample PDF run shows removed running headers and a stripped references section.
- [ ] Unit tests cover at least two noise classes (e.g. repeated footer, disclaimer keyword).

**Approach-Specific Note:** Yahya does not consume this module in Approach A until Week 2+; in Approach B, Hozaifa builds this while Yahya is already on mock retrieval.

---

### [A-HOZ-04] Semantic chunker (15% overlap)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 2 |
| File | `services/ingestion/semantic_chunker.py` |
| Complexity | L |
| Depends On | A-HOZ-03 |
| Blocks | A-HOZ-05 |
| Status | 🔲 Not Started |

**What & Why:** Sentence/paragraph-aware windows with **15% overlap** and topic-shift boundaries, matching Phase 1 chunking rules.

**Acceptance Criteria:**

- [ ] Consecutive chunks share ~15% token overlap on a fixed test document.
- [ ] Chunks break on sentence boundaries, not mid-word.
- [ ] Topic-shift heuristic documented and covered by a fixture test.

**Approach-Specific Note:** Longer critical path before formatter; Approach B runs the same risk but parallelises Yahya’s agent work during this calendar time.

---

### [A-HOZ-05] Formatter Agent (LLM integration)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 2 |
| File | `services/ingestion/formatter_agent.py` |
| Complexity | L |
| Depends On | A-HOZ-04 |
| Blocks | A-HOZ-06 |
| Status | 🔲 Not Started |

**What & Why:** Per-chunk LLM labelling (`difficulty`, `xp_reward`, `safety_risk`, `symptom_tags`, etc.) using the Phase 1 prompt strategy and labelling table.

**Acceptance Criteria:**

- [ ] Output validates against `ClinicalTask`-compatible metadata schema before upsert.
- [ ] Crisis keywords set `safety_risk = True` in a golden-file test.
- [ ] Token/cost guard (e.g. batch size cap) documented.

**Approach-Specific Note:** Approach A delays all Guild work until this exists on the real pipeline; Approach B’s mock bypasses it for demos.

> ⚠️ **Integration Risk:** Mis-labelled `safety_risk` flows into Phase 2 auditor tests—coordinate golden outputs with Yahya.

---

### [A-HOZ-06] **GATE:** ChromaDB hybrid adapter (real implementation)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 3 |
| File | `services/knowledge_base/chroma_adapter.py` |
| Complexity | L |
| Depends On | A-HOZ-01, A-HOZ-05 |
| Blocks | A-YAH-04, A-YAH-05 |
| Status | 🔲 Not Started |

**What & Why:** Persistent Chroma client, hybrid `where` / `where_document` queries, embedding model, and mapping of metadata into `ClinicalTask`—the handoff Yahya needs to drop fixtures.

**Acceptance Criteria:**

- [ ] Integration test (e.g. `tests/integration/test_chroma_adapter_real.py`) runs against a small fixture DB committed or CI-built, returning ≥5 `ClinicalTask` rows with `difficulty` and `symptom_tags` populated.
- [ ] Query path respects `RetrievalQuery.max_difficulty` and symptom filters per Phase 1–2.
- [ ] Yahya can run the same test locally after clone + env vars from `.env.example`.

**Approach-Specific Note:** This is the **only** Week 1 merge that unlocks real E2E for Yahya; Approach B uses a mock until **B-HOZ-07** instead.

> ⚠️ **Integration Risk:** Highest single merge point—schedule joint 30m verification the day **A-HOZ-06** lands.

---

### [A-HOZ-07] Integrity check script

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 3 |
| File | `scripts/verify_integrity.py` |
| Complexity | M |
| Depends On | A-HOZ-06 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Scans Chroma metadata for mandatory fields (`xp_reward`, `difficulty`, `symptom_tags`) and prints a table of violating `task_id`s.

**Acceptance Criteria:**

- [ ] Exit code non-zero when violations exist (for CI).
- [ ] Output lists `task_id` and missing field names.
- [ ] Documented in Phase 1 “Rebuild + verify” flow.

**Approach-Specific Note:** In Approach A this follows a stable real index; Approach B may run it earlier against partial indexes—ordering differs, not intent.

---

### [A-HOZ-08] `GET /health` for knowledge base

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 3 |
| File | `services/knowledge_base/router.py` |
| Complexity | S |
| Depends On | A-HOZ-06 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Exposes `indexed_tasks`, `storage_status`, `last_ingestion` per Phase 1 health spec (gateway may aggregate later).

**Acceptance Criteria:**

- [ ] JSON response matches Phase 1 shape (`indexed_tasks`, `storage_status`, `last_ingestion`).
- [ ] Returns degraded status when Chroma is empty or unreachable.
- [ ] Documented in `docs/services/microservices.md` if that file lists routes.

**Approach-Specific Note:** Approach A lands health with the real adapter in Week 2 start; Approach B schedules **B-HOZ-12** in Phase 2 week.

---

### [A-HOZ-09] Initial clinical PDF migration script

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Technical Deliverables |
| File | `scripts/migrate_initial_clinical_library.py` |
| Complexity | M |
| Depends On | A-HOZ-04, A-HOZ-05, A-HOZ-06 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** One-shot ingest from `data/clinical_pdfs/` (or configured path via `services/shared/state.py`) through PDF → chunk → formatter → Chroma.

**Acceptance Criteria:**

- [ ] Idempotent enough to re-run without duplicate IDs (or documents wipe strategy).
- [ ] Logs structured events end-to-end.
- [ ] README or `docs/services/ingestion.md` references run commands.

**Approach-Specific Note:** Completes Phase 1 “factory”; Yahya still uses fixtures until **A-HOZ-06** test passes even if migration runs later.

---

### [A-YAH-01] FastAPI scaffold and router structure

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 1 — scaffolding |
| File | `services/gateway/main.py` |
| Complexity | M |
| Depends On | A-HOZ-01 |
| Blocks | A-YAH-09, A-YAH-10 |
| Status | 🔲 Not Started |

**What & Why:** Application factory, CORS, lifespan hooks, and stub routes so later orchestration slots in without restructuring.

**Acceptance Criteria:**

- [ ] `uvicorn services.gateway.main:app` starts with `PYTHONPATH=.` documented.
- [ ] Routers mounted for assessment/architect paths or placeholders listed in OpenAPI.
- [ ] No hard dependency on Chroma in Week 1 imports.

**Approach-Specific Note:** In Approach B the same file must wire **mock** KB on Day 1 (**B-YAH-01**); here it stays Chroma-free until **A-HOZ-06**.

---

### [A-YAH-02] Profiler Agent (`UserContext`, `RetrievalQuery`, \(R_{app}\))

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 1 (logic only in Week 1) |
| File | `services/assessment/core.py` |
| Complexity | L |
| Depends On | A-HOZ-01 |
| Blocks | A-YAH-04, A-YAH-09 |
| Status | 🔲 Not Started |

**What & Why:** Implements sigmoid digital strain and normalisations from the roadmap, outputting `UserContext` and `RetrievalQuery` without calling the knowledge base.

Sigmoid:

```math
R_{app} = \frac{1}{1 + e^{-0.05 \cdot (screen\_time\_minutes - 60)}}
```

Normalisation:

```math
gad7\_normalised = \frac{gad7\_score}{21}
```

```math
phq9\_normalised = \frac{phq9\_score}{27}
```

**Acceptance Criteria:**

- [ ] Unit tests cover \(R_{app}\) at 0, 60, 120 minutes and monotonicity.
- [ ] `RetrievalQuery.boost_digital_detox` is `True` iff \(R_{app} > 0.8\).
- [ ] Top-3 `symptom_keywords` match roadmap-controlled vocabulary rules.

**Approach-Specific Note:** Week 1 is pure logic; Approach B runs the same code against mock retrieval immediately.

---

### [A-YAH-03] Hardcoded `ClinicalTask` fixture set

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 1 — scaffolding |
| File | `tests/fixtures/clinical_tasks.py` |
| Complexity | S |
| Depends On | A-HOZ-01 |
| Blocks | A-YAH-04, A-YAH-05 |
| Status | 🔲 Not Started |

**What & Why:** Ten realistic `ClinicalTask` instances spanning `difficulty` 1–5 and varied `symptom_tags`, simulating Chroma until **A-HOZ-06**.

**Acceptance Criteria:**

- [ ] Exactly ≥10 tasks; at least one `safety_risk=True` for auditor tests.
- [ ] Fixtures importable as `from tests.fixtures.clinical_tasks import SAMPLE_TASKS`.
- [ ] Documented mapping from fixture IDs to test scenarios.

**Approach-Specific Note:** **Unique to Approach A**—Approach B relies on contract tests and env-switched mock adapter instead of a separate fixture module.

---

### Phase 2 — The Guild (Yahya leads, Hozaifa supports)

After **A-HOZ-06**, Yahya replaces fixture injection with `services/knowledge_base/chroma_adapter.py`. Hozaifa extends persistence for Phase 3 while supporting adapter bugfixes.

### [A-HOZ-10] Supabase migrations (`interaction_logs`, `roadmap_mutations`)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 3 — data model (early delivery) |
| File | `supabase/migrations/YYYYMMDDHHMMSS_interaction_logs.sql` and `supabase/migrations/YYYYMMDDHHMMSS_roadmap_mutations.sql` |
| Complexity | M |
| Depends On | A-HOZ-01 |
| Blocks | A-YAH-11 |
| Status | 🔲 Not Started |

**What & Why:** Creates tables from Phase 3 (`interaction_logs`, `roadmap_mutations` with `rationale`, `pre_mutation_state`, etc.) so telemetry and mutations are ready before Director code lands.

**Acceptance Criteria:**

- [ ] SQL matches Phase 3 column lists (including `rationale` text).
- [ ] Migrations apply cleanly on empty Supabase project.
- [ ] Linked from `docs/deployment.md` or roadmap Phase 3 file.

**Approach-Specific Note:** Pulled earlier in Week 2 in Approach A; Approach B schedules **B-HOZ-10** in parallel Week 2 with more concurrent schema touchpoints.

> ⚠️ **Integration Risk:** Yahya’s telemetry task assumes these tables exist—coordinate migration apply order on shared dev DB.

---

### [A-HOZ-11] State manager (pathing + Supabase sync foundation)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 / Phase 4 — `services/shared/state.py` |
| File | `services/shared/state.py` |
| Complexity | L |
| Depends On | A-HOZ-10 |
| Blocks | A-YAH-15 (E2E sync scenarios) |
| Status | 🔲 Not Started |

**What & Why:** Extends Phase 1 pathlib layout with Supabase sync hooks, optimistic locking, and retry policy per Phase 4 `services/shared/state.py` spec (incremental delivery starting Week 2).

**Acceptance Criteria:**

- [ ] `data/clinical_pdfs/inbox|processing|archive` helpers match Phase 1 tree.
- [ ] Supabase upsert uses `version` or `updated_at` conflict detection.
- [ ] Offline retry backoff documented (1s, 2s, 4s, cap 60s).

**Approach-Specific Note:** Approach A grows this file after KB stable; Approach B’s **B-HOZ-11** lands amid mock–real swap noise.

---

### [A-YAH-04] Knowledge retrieval in pipeline (real adapter)

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 2 |
| File | `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | A-HOZ-06, A-YAH-02, A-YAH-03 |
| Blocks | A-YAH-05 |
| Status | 🔲 Not Started |

**What & Why:** Fetches top-10 candidates from `chroma_adapter`, applies `difficulty <= user_level` and `symptom_tags` overlap with `RetrievalQuery.symptom_keywords`.

**Acceptance Criteria:**

- [ ] Integration test uses real small Chroma path from CI env.
- [ ] Candidate count configurable; default 10 before rerank to top-5.
- [ ] Logs retrieval query text for debugging.

**Approach-Specific Note:** Fixture-based until **A-HOZ-06**; Approach B calls the same code path with mock from Day 1.

> ⚠️ **Integration Risk:** Hozaifa may change metadata keys (`tag_primary`, etc.)—align with Phase 1 enriched schema.

---

### [A-YAH-05] Triple-Threat reranking engine

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 2 |
| File | `services/architect/pipeline.py` |
| Complexity | L |
| Depends On | A-YAH-04 |
| Blocks | A-YAH-06, A-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Implements Phase 2 scoring with digital-detox boost when `RetrievalQuery.boost_digital_detox` is true.

```math
Score = (SemanticSimilarity \times 0.4) + (FormWeight \times 0.3) + (R_{app} \times 0.3)
```

**Acceptance Criteria:**

- [ ] Unit tests show ordering changes when `boost_digital_detox` toggles with grounding-tagged tasks.
- [ ] `FormWeight` uses Jaccard overlap on tags vs user domains.
- [ ] Top-5 output stable given fixed inputs (deterministic tie-break).

**Approach-Specific Note:** Same formula as Approach B until Phase 4 weight change; Approach A validates later in calendar time.

---

### [A-YAH-06] Gamifier Agent (XP + sequencing)

| Field | Value |
|-------|-------|
| Owner | Ahmed |
| Phase | Phase 2 — Section 3 |
| File | `services/architect/logic.py` |
| Complexity | M |
| Depends On | A-YAH-05 |
| Blocks | A-YAH-09 |
| Status | 🔲 Not Started |

**What & Why:** Applies Phase 2 XP scaling and Quick Win → ladder → Boss sequencing rules.

```math
xp\_{reward}^{final} = BaseXP \times difficulty \times (1 + user\_level \times 0.1)
```

**Acceptance Criteria:**

- [ ] First task is `difficulty=1` with highest eligible XP among safe tasks.
- [ ] Final task picks highest difficulty among safe candidates.
- [ ] Unit tests cover three-slot and five-slot roadmaps.

**Approach-Specific Note:** Uses real task stats post–**A-HOZ-06**; Approach B exercises the same logic on mock tasks first.

---

### [A-YAH-07] Clinical Auditor and safety gate

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 4 |
| File | `services/architect/auditor.py` |
| Complexity | L |
| Depends On | A-YAH-06 |
| Blocks | A-YAH-09, A-YAH-12 |
| Status | 🔲 Not Started |

**What & Why:** Empathy check, crisis keyword guardrails (EN/AR lists from Phase 2), emergency override payload—no client response bypasses this gate.

**Acceptance Criteria:**

- [ ] RED path returns hotline structure from Phase 2 emergency object table.
- [ ] CI tests for green / yellow / red / Arabic keyword paths.
- [ ] `safety_risk=True` on any task forces override.

**Approach-Specific Note:** Highest safety priority in both approaches; Approach A has fewer moving parts in Week 1 but later E2E stress.

> ⚠️ **Integration Risk:** Formatter `safety_risk` and auditor keywords must stay aligned with clinical review.

---

### [A-YAH-08] Arabic + English localisation constants

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 4 |
| File | `services/architect/i18n.py` |
| Complexity | S |
| Depends On | A-YAH-07 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Centralises crisis strings, hotline labels, and auditor messages per Phase 2 locale requirements.

**Acceptance Criteria:**

- [ ] Constants imported only from this module inside `auditor.py`.
- [ ] At least one test uses `locale="ar"` path.
- [ ] No hard-coded Arabic strings elsewhere in auditor.

**Approach-Specific Note:** Approach B schedules this in Phase 2 week (**B-YAH-09**) after mock swap; Approach A can land with auditor in same week.

---

### [A-YAH-09] Full orchestration chain in gateway

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 5 |
| File | `services/gateway/main.py` |
| Complexity | M |
| Depends On | A-YAH-01, A-YAH-02, A-YAH-05, A-YAH-06, A-YAH-07 |
| Blocks | A-YAH-10, A-YAH-11 |
| Status | 🔲 Not Started |

**What & Why:** Wires Profiler → Architect (`pipeline.py`) → Gamifier (`logic.py`) → Auditor (`auditor.py`) per Phase 2 orchestration diagram.

**Acceptance Criteria:**

- [ ] Single request path exercises all four stages with structured logging.
- [ ] Exceptions from KB return safe JSON error, not stack traces to client.
- [ ] OpenAPI documents request/response models.

**Approach-Specific Note:** E2E possible only after **A-HOZ-06**; Approach B achieves a mock E2E in Week 1.

> ⚠️ **Integration Risk:** Gateway changes overlap with Hozaifa health/telemetry routes—coordinate file ownership or use small PRs.

---

### [A-YAH-10] `POST /api/roadmap` validated response

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 5 |
| File | `services/gateway/main.py` |
| Complexity | S |
| Depends On | A-YAH-09 |
| Blocks | A-YAH-15 |
| Status | 🔲 Not Started |

**What & Why:** Public contract for roadmap generation with response validation against `FinalRoadmap`-equivalent schema (per shared schemas / OpenAPI).

**Acceptance Criteria:**

- [ ] Happy path returns 200 with tasks array and overview.
- [ ] Crisis path returns RED payload per Phase 2.
- [ ] Contract snapshot test prevents accidental field removal.

**Approach-Specific Note:** Lands end of Week 2; Approach B targets end of Week 1 with mock data (**B-YAH-07**).

---

### Phase 3 — The Director (Hozaifa leads, Yahya adds telemetry)

### [A-HOZ-12] Director evaluator (`PerformanceReport`)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 3 — Section 2 |
| File | `services/director/evaluator.py` |
| Complexity | L |
| Depends On | A-HOZ-10 |
| Blocks | A-HOZ-13 |
| Status | 🔲 Not Started |

**What & Why:** Computes Engagement Rate, Clinical Velocity, Sentiment Trend per Phase 3 thresholds on `interaction_logs` + frustration signals.

**Acceptance Criteria:**

- [ ] Schedulable every 7 days or after 5 completions (configurable).
- [ ] Emits `PerformanceReport` with boolean failure flags.
- [ ] Unit tests with synthetic event series.

**Approach-Specific Note:** Starts Week 3 after stable Guild; Approach B overlaps with **B-HOZ-13** during Week 2 tail.

---

### [A-HOZ-13] Mutation engine (Downgrade + Promotion)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 3 — Section 2 |
| File | `services/director/mutation_engine.py` |
| Complexity | L |
| Depends On | A-HOZ-12 |
| Blocks | A-YAH-13 |
| Status | 🔲 Not Started |

**What & Why:** Emits structured `MutationInstruction` / Director directive JSON (max difficulty, XP multiplier, validity window) and persists to `roadmap_mutations`.

**Acceptance Criteria:**

- [ ] Downgrade pivot matches Phase 3 JSON example semantics.
- [ ] Promotion unlocks difficulty 4–5 and shifts tag priority per spec.
- [ ] Row written to `roadmap_mutations` with `rationale`.

**Approach-Specific Note:** Yahya’s pipeline must read these instructions—serialised contract must match **A-YAH-13**.

> ⚠️ **Integration Risk:** `MutationInstruction` shape is shared; version the JSON schema in `services/shared/schemas.py` if needed.

---

### [A-YAH-11] `POST /api/telemetry`

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 3 — Section 1 |
| File | `services/gateway/main.py` |
| Complexity | M |
| Depends On | A-HOZ-10 |
| Blocks | A-HOZ-12 |
| Status | 🔲 Not Started |

**What & Why:** Accepts Phase 3 payload (`task_id`, `interaction_type`, `completion_time`, `drop_off_point`, `xp_earned`) and inserts into **`interaction_logs`** (Phase 3 roadmap); Phase 4 `user_interactions` can mirror or migrate forward per Phase 4 doc.

**Acceptance Criteria:**

- [ ] Validates enums `VIEWED|STARTED|COMPLETED|SKIPPED`.
- [ ] Persists `user_id` from auth context and server timestamp.
- [ ] Returns 204/200 with idempotent dedupe key optional.

**Approach-Specific Note:** Depends on real Supabase migrations first; Approach B same dependency with tighter calendar overlap.

> ⚠️ **Integration Risk:** Hozaifa owns schema; Yahya owns HTTP—align on nullability and FK to users table.

---

### [A-YAH-12] Sentiment hook + `frustration_score`

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 3 — Section 1 |
| File | `services/architect/auditor.py` |
| Complexity | M |
| Depends On | A-YAH-07 |
| Blocks | A-HOZ-12 |
| Status | 🔲 Not Started |

**What & Why:** Lightweight classifier on chat feedback; `frustration_score > 0.7` sets AMBER advisory for Director per Phase 3.

**Acceptance Criteria:**

- [ ] Output stored or forwarded with timestamp and user id.
- [ ] Does not override Phase 2 RED crisis path.
- [ ] Version pin for model/rules documented.

**Approach-Specific Note:** Same clinical constraints as **B-YAH-12**; Approach A validates after auditor baseline is stable.

---

### [A-YAH-13] Director override read in pipeline

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 3 — Section 2 |
| File | `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | A-HOZ-13 |
| Blocks | A-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Before retrieval, loads active `MutationInstruction` (max difficulty, XP multiplier, tag focus) and constrains `RetrievalQuery` / filters.

**Acceptance Criteria:**

- [ ] When directive says `max_difficulty: 2`, no task with difficulty >2 returned pre-auditor.
- [ ] Expired directives ignored using `valid_until`.
- [ ] Unit test with stubbed Supabase/Director client.

**Approach-Specific Note:** Tight coupling to Hozaifa’s mutation writer—Approach B has same coupling earlier in calendar (**B-YAH-13**).

> ⚠️ **Integration Risk:** Both developers touch `pipeline.py` across phases; use feature flags or short-lived branches.

---

### Phase 4 — Self-refining loop (both converge)

### [A-HOZ-14] `utility_score` increment on `COMPLETED`

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 4 — Section 3 |
| File | `services/knowledge_base/chroma_adapter.py` |
| Complexity | M |
| Depends On | A-HOZ-06, A-YAH-11 |
| Blocks | A-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Debounced metadata updates implementing:

```math
utility\_score\_{new} = utility\_score\_{old} + (0.1 \times engagement\_quality)
```

```math
engagement\_quality = \frac{engagement\_time}{expected\_time} \times (1 - frustration\_score)
```

**Acceptance Criteria:**

- [ ] Batch or debounce limits Chroma writes ≤N/sec configurable.
- [ ] Integration test updates one task’s metadata and reads it back.
- [ ] Documented interaction with formatter baseline scores.

**Approach-Specific Note:** Approach A lands Week 4 cleanly; Approach B packs into Week 3 (**B-HOZ-15**).

> ⚠️ **Integration Risk:** Metadata mutation races with concurrent reads during roadmap generation—use snapshot or versioning policy.

---

### [A-HOZ-15] Full mutation logic + `interest_profile`

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 4 — Section 2 |
| File | `services/director/mutation_logic.py` |
| Complexity | L |
| Depends On | A-HOZ-13, A-HOZ-10 |
| Blocks | A-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Downgrade, Pivot on modality skips/completions, persistent `interest_profile` JSON per Phase 4 schema.

**Acceptance Criteria:**

- [ ] Pivot updates `modality_weights` / `tag_boosts` with optimistic `version`.
- [ ] Supabase migration for `user_interactions` / profile extensions per Phase 4 deliverables.
- [ ] Unit tests for journaling skipped + breathing completed scenario.

**Approach-Specific Note:** Approach B consolidates as **B-HOZ-16** in accelerated Week 3.

---

### [A-YAH-14] Triple-Threat v2 (add `UtilityScore`)

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 4 — Section 3 |
| File | `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | A-HOZ-14, A-YAH-05 |
| Blocks | A-YAH-15 |
| Status | 🔲 Not Started |

**What & Why:** Replaces Phase 2 weights with Phase 4 four-term formula:

```math
Score = (SemanticSimilarity \times 0.35) + (FormWeight \times 0.25) + (R_{app} \times 0.25) + (UtilityScore \times 0.15)
```

**Acceptance Criteria:**

- [ ] `UtilityScore` normalised to [0,1] before weighting.
- [ ] Regression tests show ordering changes when utility differs at fixed similarity.
- [ ] RED safety path still bypasses ranking games.

**Approach-Specific Note:** Same as **B-YAH-14** but one week later on calendar.

---

### [A-YAH-15] 14-day E2E simulation test

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 4 — Success metric |
| File | `tests/integration/test_roadmap_evolution_14d.py` (or equivalent) |
| Complexity | L |
| Depends On | A-YAH-14, A-HOZ-15, A-HOZ-11 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Validates Phase 4 success metric: statistically visible difference between first and third roadmap for a scripted user.

**Acceptance Criteria:**

- [ ] Scripted telemetry drives Director mutations across 14 simulated days.
- [ ] Asserts difficulty, modality, or tone shift between generation 1 and 3.
- [ ] Documented seed and thresholds in test docstring.

**Approach-Specific Note:** Approach B runs **B-YAH-15** in Week 3 with Week 4 buffer for flake hardening.

---

## Section 4 — Approach A sprint timeline

### Week summary

| Week | Theme | Hozaifa focus | Yahya focus |
|------|-------|---------------|-------------|
| Week 1 | Factory floor | A-HOZ-01 → A-HOZ-06 | A-YAH-01, A-YAH-02, A-YAH-03 |
| Week 2 | The Guild | A-HOZ-07 → A-HOZ-11 | A-YAH-04 → A-YAH-10 |
| Week 3 | The Director | A-HOZ-12, A-HOZ-13 | A-YAH-11 → A-YAH-13 |
| Week 4 | Self-refining | A-HOZ-14, A-HOZ-15 | A-YAH-14, A-YAH-15 |

### Week 1 — Factory floor

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | A-HOZ-01: schemas | A-YAH-01: FastAPI scaffold |
| Tue | A-HOZ-02 logging, A-HOZ-03 PDF utils start | A-YAH-02: Profiler + tests |
| Wed | A-HOZ-03 finish, A-HOZ-04 chunker start | A-YAH-02 finish, A-YAH-03 fixtures |
| Thu | A-HOZ-04 finish, A-HOZ-05 formatter start | A-YAH-03 review + pipeline stubs (no Chroma) |
| Fri | A-HOZ-05 finish, A-HOZ-06 start | Unit tests only; prep integration checklist |

**End-of-Week Gate:** **A-HOZ-06** merged with passing integration test Yahya can run; otherwise Yahya continues fixture-only work and flags slip risk.

### Week 2 — The Guild

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | A-HOZ-06 complete + handoff session | A-YAH-04: real retrieval |
| Tue | A-HOZ-07 integrity script | A-YAH-05: Triple-Threat |
| Wed | A-HOZ-08 health | A-YAH-06: Gamifier (Ahmed) |
| Thu | A-HOZ-09 migration, A-HOZ-10 migrations start | A-YAH-07: Auditor |
| Fri | A-HOZ-10/11 complete | A-YAH-08 i18n, A-YAH-09 orchestration, A-YAH-10 roadmap endpoint |

**End-of-Week Gate:** `POST /api/roadmap` passes smoke on real Chroma; `GET /health` green; Supabase migrations applied to dev.

### Week 3 — The Director

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | A-HOZ-12 evaluator start | A-YAH-11 telemetry |
| Tue | A-HOZ-12 finish | A-YAH-12 sentiment hook |
| Wed | A-HOZ-13 mutation engine | A-YAH-13 pipeline overrides |
| Thu | Joint test: Downgrade pivot end-to-end | Joint test: telemetry → mutation → retrieval |
| Fri | Hardening + bugfix buffer | Hardening + bugfix buffer |

**End-of-Week Gate:** Synthetic user triggers Downgrade directive; pipeline respects `max_difficulty` for 48h window.

### Week 4 — Self-refining

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | A-HOZ-14 utility increment | A-YAH-14 Triple-Threat v2 |
| Tue | A-HOZ-15 mutation_logic + profile | A-YAH-14 tests |
| Wed | Supabase Phase 4 migration alignment | A-YAH-15 simulation harness |
| Thu | Performance + Chroma write tuning | A-YAH-15 assertions + flake fixes |
| Fri | Integration checkpoint | Integration checkpoint |

**End-of-Week Gate:** Phase 4 success metric test passes on CI or documented manual run; utility updates visible in metadata.

---

## Section 5 — Approach A risk register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| A-HOZ-06 delayed → Yahya blocked | Medium | High | A-YAH-03 fixtures absorb ~2 days; reduce scope of Week 2 E2E |
| Formatter LLM cost spike | Low | Medium | Batch size cap (e.g. 20 chunks); cache formatter outputs by chunk hash |
| Schema change after A-HOZ-01 | Low | Critical | Dual approval on `services/shared/schemas.py` PRs |
| Safety gate bypass in CI | Low | Critical | Auditor tests required on every PR touching `services/gateway/main.py` or `services/architect/auditor.py` |
