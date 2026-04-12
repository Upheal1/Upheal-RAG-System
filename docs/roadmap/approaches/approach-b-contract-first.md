# Approach B — Contract-First (parallel sprint)

## Section 1 — Overview

**Name:** Contract-First (parallel sprint)  
**Metaphor:** “Agree on the blueprint, then build all floors simultaneously.”  
**Core principle:** On Day 1, schemas, the knowledge-base **public façade**, and `MutationInstruction` (Phase 3) are frozen. Hozaifa ships a **mock** implementation that satisfies the contract; Yahya imports the same symbols from `services/knowledge_base/chroma_adapter.py` (resolved via `USE_MOCK_ADAPTER`). The real Chroma hybrid adapter replaces internals after **B-HOZ-07** passes `tests/contracts/test_adapter_contract.py`—ideally without changing Yahya’s call sites.

**When to choose this approach**

- The pair has collaborated before and can sync quickly.  
- A demo or investor milestone is **≤3 weeks**.  
- Both are comfortable enforcing strict contract tests.

> 💡 **Approach Advantage:** Yahya can ship a working `POST /api/roadmap` on **mock** data by end of Week 1—roughly one week earlier than Approach A’s real-vector E2E.

> 🔴 **Approach Trade-off:** If the real `chroma_adapter` diverges on edge cases (empty collection, malformed metadata, embedding failures), Yahya’s agents may pass all unit tests yet fail in production—contract breadth is the mitigation, not optional.

---

## Section 2 — Role definitions in this approach

**Hozaifa — “The contract keeper”**  
Day 1 delivers **B-HOZ-01**: locked `services/shared/schemas.py` plus a mock-backed `services/knowledge_base/chroma_adapter.py` façade (implementation may delegate to `services/knowledge_base/chroma_adapter_mock.py`). Then builds the real ingestion stack and **B-HOZ-07** real adapter behind the same signatures.

**Yahya — “The parallel builder”**  
Never imports `chroma_adapter_mock` directly—only the façade module. Sets `USE_MOCK_ADAPTER=true` until the swap task **B-YAH-08**.

---

## Section 3 — Contract-first setup (unique to Approach B)

Before phase execution, hold a **contract session** (synchronous, time-boxed) producing three locked artifacts.

### Artifact 1 — Locked schemas (`services/shared/schemas.py`)

- All models from Phase 1 (`ClinicalTask`, `UserContext`, `RetrievalQuery`) plus Phase 3 **`MutationInstruction`** / Director directive fields required by `services/architect/pipeline.py` are defined.  
- **Freeze protocol:** Adding/removing/renaming a field requires (1) written agreement in stand-up notes, (2) PR labelled `contract-change`, (3) simultaneous update to `tests/contracts/test_adapter_contract.py`, (4) both developers approving the PR.

> ⚠️ **Integration Risk:** Schema drift breaks mock–real parity faster than in Approach A—no freeze discipline means Week 2 collapse.

### Artifact 2 — Mock adapter (`services/knowledge_base/chroma_adapter_mock.py`)

Implements the **same public API** as the real hybrid adapter. The façade in `services/knowledge_base/chroma_adapter.py` selects mock vs real using `USE_MOCK_ADAPTER` (string `true`/`1`).

| Method | Mock behaviour |
|--------|----------------|
| `search(query, filters)` | Returns a hardcoded list of 10 `ClinicalTask` objects sorted by a deterministic fake similarity score; `filters` must accept `max_difficulty` and optional tag lists mirroring Phase 1–2 hybrid intent |
| `get_by_id(task_id)` | Returns the seeded `ClinicalTask` whose `task_id` matches, else raises `TaskNotFoundError` |
| `update_utility_score(task_id, delta)` | No-op on stored data; logs structured JSON per Phase 1 logging rules for later assertion |

**Note:** The Phase 1 roadmap describes hybrid Chroma querying; `search` is the **contract façade** that the real implementation backs with embeddings plus `where` / `where_document`. Naming aligns with Approach B delivery spec; the real class may internally call `retrieve_tasks`-style logic.

**Mock acceptance checklist**

- [ ] `from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase` (or agreed class name) works with mock when `USE_MOCK_ADAPTER=true`.
- [ ] At least **10** seeded `ClinicalTask` rows span `difficulty` 1–5 and multiple `symptom_tags`.
- [ ] Raises **`TaskNotFoundError`** (or agreed typed exception) for unknown UUIDs so Yahya handles errors from Day 1.
- [ ] Seeded data copied from one real formatted chunk **on Day 1** (Hozaifa) so tensor shapes and string lengths resemble production.

### Artifact 3 — Contract test suite (`tests/contracts/test_adapter_contract.py`)

Both mock and real adapters **must pass identical parametrized tests** before **B-YAH-08** swap.

**Required test cases**

- [ ] `search` returns ≤ requested `top_k`, non-empty when filters match seed data, empty when `max_difficulty` excludes all.
- [ ] `search` respects tag filter: when filters require `"anxiety"`, no task without overlapping `symptom_tags`.
- [ ] `get_by_id` returns equal payloads for mock and real given the same seeded id (real adapter uses fixture DB with same ids loaded).
- [ ] `get_by_id` raises `TaskNotFoundError` for random UUID on both implementations.
- [ ] `update_utility_score` does not throw on either implementation; real implementation additionally verifies metadata change after call (post–B-HOZ-07).
- [ ] Concurrent `search` calls (10 threads) complete without process crash on mock (thread-safety smoke).

> ⚠️ **Integration Risk:** This file is the **single highest-leverage** artifact in Approach B; gaps here cause silent regressions at mock→real swap.

---

## Section 4 — Approach B phase mapping

### Phase 1 — Knowledge infrastructure (parallel from Day 1)

In Approach B, Phase 1 is **not** a hard blocker for Yahya: mock-backed `search` unblocks `services/architect/pipeline.py` immediately while Hozaifa builds PDF → chunk → formatter → real Chroma.

### [B-HOZ-01] Lock schemas + mock-backed façade (Day 1)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — contract session |
| File | `services/shared/schemas.py`, `services/knowledge_base/chroma_adapter.py`, `services/knowledge_base/chroma_adapter_mock.py` |
| Complexity | L |
| Depends On | None |
| Blocks | B-HOZ-02, B-YAH-01, B-YAH-02, B-YAH-03 |
| Status | 🔲 Not Started |

**What & Why:** Delivers **Artifact 1** and **Artifact 2** together so Yahya’s imports resolve on Day 1—unlike Approach A where **A-HOZ-01** and fixtures are separate lanes.

**Acceptance Criteria:**

- [ ] `ClinicalTask`, `UserContext`, `RetrievalQuery` match Phase 1 field tables.
- [ ] Mock `search` / `get_by_id` / `update_utility_score` implemented per Artifact 2 table.
- [ ] `USE_MOCK_ADAPTER` toggles mock without changing Yahya’s import path.

**Approach-Specific Note:** **Combined** schema + mock delivery; Approach A splits **A-HOZ-01** from any mock (Yahya uses static fixtures instead).

> ⚠️ **Integration Risk:** Yahya starts **B-YAH-03** immediately—any schema bug blocks both developers.

---

### [B-HOZ-02] Contract test suite

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — contract session |
| File | `tests/contracts/test_adapter_contract.py` |
| Complexity | M |
| Depends On | B-HOZ-01 |
| Blocks | B-HOZ-07, B-YAH-08 |
| Status | 🔲 Not Started |

**What & Why:** Implements **Artifact 3** test list so mock and real adapters stay substitutable.

**Acceptance Criteria:**

- [ ] All bullet tests from Section 3 implemented with `@pytest.mark.parametrize("adapter", [...])`.
- [ ] CI job `pytest tests/contracts/` required on main.
- [ ] Failure output prints which adapter implementation broke.

**Approach-Specific Note:** Approach A has no parallel file—integration is proven by **A-HOZ-06** integration test only.

---

### [B-HOZ-03] Structured JSON logger

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 1 |
| File | `services/shared/logging.py` |
| Complexity | S |
| Depends On | B-HOZ-01 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-02**—structured logs for ingestion and mock `update_utility_score` verification.

**Acceptance Criteria:**

- [ ] JSON lines include `timestamp`, `service`, `event`, `payload`.
- [ ] Mock adapter logs `kb.mock.utility_update` events.

**Approach-Specific Note:** Must land early so Week 1 debugging compares Yahya vs Hozaifa logs consistently.

---

### [B-HOZ-04] PDF extraction and noise filter

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 2 |
| File | `services/ingestion/pdf_utils.py` |
| Complexity | M |
| Depends On | B-HOZ-03 |
| Blocks | B-HOZ-05 |
| Status | 🔲 Not Started |

**What & Why:** Same scope as **A-HOZ-03**, built while Yahya uses mock retrieval.

**Acceptance Criteria:**

- [ ] Same as A-HOZ-03 acceptance criteria.

**Approach-Specific Note:** Parallel calendar with **B-YAH-03**–**B-YAH-05** increases context switching for Hozaifa.

---

### [B-HOZ-05] Semantic chunker (15% overlap)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 2 |
| File | `services/ingestion/semantic_chunker.py` |
| Complexity | L |
| Depends On | B-HOZ-04 |
| Blocks | B-HOZ-06 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-04**.

**Acceptance Criteria:**

- [ ] Same as A-HOZ-04 acceptance criteria.

**Approach-Specific Note:** Risk that Yahya demos on mock data that does not reflect chunk boundaries—mitigate with Day 1 real sample in mock seed.

---

### [B-HOZ-06] Formatter Agent (LLM)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 2 |
| File | `services/ingestion/formatter_agent.py` |
| Complexity | L |
| Depends On | B-HOZ-05 |
| Blocks | B-HOZ-07 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-05**.

**Acceptance Criteria:**

- [ ] Same as A-HOZ-05 acceptance criteria.

**Approach-Specific Note:** Yahya’s **B-YAH-06** auditor tests may assume formatter outputs—coordinate `safety_risk` golden cases.

> ⚠️ **Integration Risk:** Formatter labelling and auditor expectations must match before investor demo.

---

### [B-HOZ-07] Real Chroma hybrid adapter (replaces mock)

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 3 |
| File | `services/knowledge_base/chroma_adapter.py` |
| Complexity | L |
| Depends On | B-HOZ-01, B-HOZ-02, B-HOZ-06 |
| Blocks | B-YAH-08 |
| Status | 🔲 Not Started |

**What & Why:** Real persistent Chroma + embeddings implementing `search` / `get_by_id` / `update_utility_score` semantics; passes **B-HOZ-02** suite on CI fixture DB.

**Acceptance Criteria:**

- [ ] All contract tests green with `USE_MOCK_ADAPTER=false`.
- [ ] Hybrid `where` / `where_document` behaviour documented in module docstring (Phase 1).
- [ ] Performance baseline recorded (p95 `search` latency).

**Approach-Specific Note:** This is Approach B’s **A-HOZ-06** equivalent but lands **end of Week 2** target, not Week 1 gate.

> ⚠️ **Integration Risk:** Highest swap risk—contract tests must be exhaustive before **B-YAH-08**.

---

### [B-HOZ-08] Integrity check script

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 3 |
| File | `scripts/verify_integrity.py` |
| Complexity | M |
| Depends On | B-HOZ-07 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-07**.

**Acceptance Criteria:**

- [ ] Same as A-HOZ-07 acceptance criteria.

**Approach-Specific Note:** Runs against real index post-swap; mock phase skips or no-ops with clear message.

---

### [B-HOZ-09] Initial clinical PDF migration

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — deliverables |
| File | `scripts/migrate_initial_clinical_library.py` |
| Complexity | M |
| Depends On | B-HOZ-05, B-HOZ-06, B-HOZ-07 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-09**.

**Acceptance Criteria:**

- [ ] Same as A-HOZ-09 acceptance criteria.

**Approach-Specific Note:** May run in parallel with **B-YAH-08** verification week.

---

### [B-YAH-01] FastAPI scaffold (mock wired)

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 1 — parallel |
| File | `services/gateway/main.py` |
| Complexity | M |
| Depends On | B-HOZ-01 |
| Blocks | B-YAH-07 |
| Status | 🔲 Not Started |

**What & Why:** Application shell with KB client bound to mock via `USE_MOCK_ADAPTER=true` by default in dev `.env.example`.

**Acceptance Criteria:**

- [ ] Health stub returns 200.
- [ ] Dependency injection provides KB singleton compatible with `search` signature.
- [ ] Documented env flag in `docs/getting-started.md`.

**Approach-Specific Note:** Unlike **A-YAH-01**, mock KB is live on Day 1.

> ⚠️ **Integration Risk:** Gateway and Hozaifa may both touch `main.py` for telemetry later—establish file ownership rules.

---

### [B-YAH-02] Profiler Agent (full)

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 1 |
| File | `services/assessment/core.py` |
| Complexity | L |
| Depends On | B-HOZ-01 |
| Blocks | B-YAH-03 |
| Status | 🔲 Not Started |

**What & Why:** Implements \(R_{app}\) and normalisations per Phase 2.

```math
R_{app} = \frac{1}{1 + e^{-0.05 \cdot (screen\_time\_minutes - 60)}}
```

```math
gad7\_normalised = \frac{gad7\_score}{21}
```

```math
phq9\_normalised = \frac{phq9\_score}{27}
```

**Acceptance Criteria:**

- [ ] Same numerical tests as **A-YAH-02**.
- [ ] `RetrievalQuery` consumed by `search` without type coercion hacks.

**Approach-Specific Note:** Full implementation Week 1, not fixture-only.

---

### [B-YAH-03] Knowledge retrieval via `search`

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 2 |
| File | `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | B-YAH-02, B-HOZ-01 |
| Blocks | B-YAH-04 |
| Status | 🔲 Not Started |

**What & Why:** Calls façade `search` with `RetrievalQuery` and `UserContext` derived filters; retrieves top-10 before rerank.

**Acceptance Criteria:**

- [ ] Works with mock env in CI without Chroma binary.
- [ ] Logs query text and filter dict for debugging.
- [ ] Contract test optionally imports pipeline helper for smoke (optional).

**Approach-Specific Note:** **B-YAH-04** must not edit conflicting regions—sequential PRs per risk register.

> ⚠️ **Integration Risk:** Merge conflicts on `pipeline.py` if **B-YAH-03** and **B-YAH-04** branch diverge; stack PRs.

---

### [B-YAH-04] Triple-Threat reranking

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 2 |
| File | `services/architect/pipeline.py` |
| Complexity | L |
| Depends On | B-YAH-03 |
| Blocks | B-YAH-05, B-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Phase 2 formula and digital-detox boost.

```math
Score = (SemanticSimilarity \times 0.4) + (FormWeight \times 0.3) + (R_{app} \times 0.3)
```

**Acceptance Criteria:**

- [ ] Same behavioural tests as **A-YAH-05** using mock `search` outputs.
- [ ] Deterministic ordering given fixed mock seed.

**Approach-Specific Note:** Validated Week 1 on mock similarities; real embeddings may change ordering—**B-YAH-08** re-runs full suite.

---

### [B-YAH-05] Gamifier Agent

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 3 |
| File | `services/architect/logic.py` |
| Complexity | M |
| Depends On | B-YAH-04 |
| Blocks | B-YAH-07 |
| Status | 🔲 Not Started |

**What & Why:** Phase 2 XP and sequencing.

```math
xp\_{reward}^{final} = BaseXP \times difficulty \times (1 + user\_level \times 0.1)
```

**Acceptance Criteria:**

- [ ] Same as **A-YAH-06** acceptance criteria.

**Approach-Specific Note:** Uses mock task payloads first; real swap should not require logic changes.

---

### [B-YAH-06] Clinical Auditor (safety gate)

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 4 |
| File | `services/architect/auditor.py` |
| Complexity | L |
| Depends On | B-YAH-05 |
| Blocks | B-YAH-07, B-YAH-12 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-YAH-07**—highest safety priority.

**Acceptance Criteria:**

- [ ] Same as **A-YAH-07** acceptance criteria.

**Approach-Specific Note:** Demo may show crisis path on mock tasks—ensure copy matches Phase 2 i18n tables.

> ⚠️ **Integration Risk:** Clinical wording must be reviewed before external demo.

---

### [B-YAH-07] `POST /api/roadmap` on mock (Week 1 demo)

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 5 |
| File | `services/gateway/main.py` |
| Complexity | M |
| Depends On | B-YAH-01, B-YAH-02, B-YAH-04, B-YAH-05, B-YAH-06 |
| Blocks | B-YAH-10 |
| Status | 🔲 Not Started |

**What & Why:** End-to-end Guild chain returning a validated roadmap using mock KB—**~7 days earlier** than Approach A real-vector milestone.

**Acceptance Criteria:**

- [ ] Demo script documented (curl / Bruno).
- [ ] OpenAPI includes `POST /api/roadmap`.
- [ ] Crisis override test passes on mock data.

**Approach-Specific Note:** **Unique Week 1 demo surface**; Approach A only reaches this after **A-HOZ-06**.

---

### Phase 2 — Guild: mock → real swap

Critical event: **B-HOZ-07** green, then **B-YAH-08** flips env and re-runs contract + E2E tests.

### [B-HOZ-10] Supabase migrations

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 3 — data model |
| File | `supabase/migrations/YYYYMMDDHHMMSS_interaction_logs.sql`, `supabase/migrations/YYYYMMDDHHMMSS_roadmap_mutations.sql` |
| Complexity | M |
| Depends On | B-HOZ-01 |
| Blocks | B-YAH-11 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-10**.

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-10** acceptance criteria.

**Approach-Specific Note:** Landed during Week 2 parallel to swap/hardening—higher chance of DB drift vs Approach A’s calmer Week 2.

> ⚠️ **Integration Risk:** Shared dev Supabase must be migrated before Yahya’s telemetry merges.

---

### [B-HOZ-11] State manager

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 / Phase 4 |
| File | `services/shared/state.py` |
| Complexity | L |
| Depends On | B-HOZ-10 |
| Blocks | B-YAH-15 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-11**.

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-11** acceptance criteria.

**Approach-Specific Note:** Overlaps swap week—schedule explicit merge order.

---

### [B-HOZ-12] `GET /health`

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 1 — Section 3 |
| File | `services/knowledge_base/router.py` |
| Complexity | S |
| Depends On | B-HOZ-07 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-08**.

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-08** acceptance criteria.

**Approach-Specific Note:** Deferred until real adapter lands—unlike Approach A where it follows **A-HOZ-07** in the same Week 2 lane.

---

### [B-YAH-08] Mock-to-real adapter swap

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — integration |
| File | `services/gateway/main.py`, `tests/contracts/test_adapter_contract.py` (re-run only) |
| Complexity | M |
| Depends On | B-HOZ-07, B-HOZ-02 |
| Blocks | B-YAH-10 |
| Status | 🔲 Not Started |

**What & Why:** Set `USE_MOCK_ADAPTER=false`, run contract suite + roadmap E2E on CI Chroma fixture; fix regressions without changing agent business logic if contract held.

**Acceptance Criteria:**

- [ ] Zero contract test regressions vs mock baseline.
- [ ] `POST /api/roadmap` smoke on real collection documented.
- [ ] Rollback playbook: flip env + open incident note if p95 latency > SLO.

**Approach-Specific Note:** **Central swap task**—no analogue in Approach A (continuous real adapter growth).

> ⚠️ **Integration Risk:** If failures appear, split “infra” vs “agent” bugs using contract tests first.

---

### [B-YAH-09] Arabic + English i18n constants

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 4 |
| File | `services/architect/i18n.py` |
| Complexity | S |
| Depends On | B-YAH-06 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-YAH-08**.

**Acceptance Criteria:**

- [ ] Same as **A-YAH-08** acceptance criteria.

**Approach-Specific Note:** Scheduled post-swap Week 2; Approach A may land same week as auditor.

---

### [B-YAH-10] End-to-end verification on real Chroma

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 5 |
| File | `services/gateway/main.py`, `tests/integration/test_roadmap_e2e.py` |
| Complexity | M |
| Depends On | B-YAH-08, B-YAH-07 |
| Blocks | B-YAH-15 |
| Status | 🔲 Not Started |

**What & Why:** Confirms full Guild chain against real indexed data and health endpoints.

**Acceptance Criteria:**

- [ ] CI job with Chroma fixture (or self-hosted runner) optional but documented.
- [ ] Digital-detox success scenario (Phase 2 success metric) automated.
- [ ] Logs correlated across gateway + KB.

**Approach-Specific Note:** Approach A collapses **A-YAH-09/10** into Week 2 without a prior mock demo milestone.

---

### Phase 3 — The Director

### [B-HOZ-13] Director evaluator

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 3 — Section 2 |
| File | `services/director/evaluator.py` |
| Complexity | L |
| Depends On | B-HOZ-10 |
| Blocks | B-HOZ-14 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-12** but may start during late Week 2 while Yahya finishes swap.

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-12** acceptance criteria.

**Approach-Specific Note:** Parallelism increases context switching versus Approach A Week 3 focus block.

---

### [B-HOZ-14] Mutation engine

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 3 — Section 2 |
| File | `services/director/mutation_engine.py` |
| Complexity | L |
| Depends On | B-HOZ-13 |
| Blocks | B-YAH-13 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-13**.

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-13** acceptance criteria.

**Approach-Specific Note:** Yahya may still be fixing swap flakes—coordinate freeze windows.

> ⚠️ **Integration Risk:** `MutationInstruction` JSON must match **B-YAH-13** expectations.

---

### [B-YAH-11] `POST /api/telemetry`

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 3 — Section 1 |
| File | `services/gateway/main.py` |
| Complexity | M |
| Depends On | B-HOZ-10 |
| Blocks | B-HOZ-13 |
| Status | 🔲 Not Started |

**What & Why:** Persists Phase 3 telemetry to **`interaction_logs`** (aligned with Phase 3 roadmap); Phase 4 `user_interactions` per Phase 4 doc can be added in **B-HOZ-16** migration wave.

**Acceptance Criteria:**

- [ ] Same as **A-YAH-11** acceptance criteria.

**Approach-Specific Note:** Lands while swap stabilization may still be active—higher merge conflict rate.

> ⚠️ **Integration Risk:** Same schema/HTTP split as Approach A.

---

### [B-YAH-12] Sentiment hook

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 3 — Section 1 |
| File | `services/architect/auditor.py` |
| Complexity | M |
| Depends On | B-YAH-06 |
| Blocks | B-HOZ-13 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-YAH-12**.

**Acceptance Criteria:**

- [ ] Same as **A-YAH-12** acceptance criteria.

**Approach-Specific Note:** None material vs Approach A beyond calendar compression.

---

### [B-YAH-13] Director override in pipeline

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 3 — Section 2 |
| File | `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | B-HOZ-14 |
| Blocks | B-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-YAH-13**.

**Acceptance Criteria:**

- [ ] Same as **A-YAH-13** acceptance criteria.

**Approach-Specific Note:** Same `pipeline.py` contention risk—use stacked branches.

> ⚠️ **Integration Risk:** Concurrent edits with **B-YAH-14** later—merge quickly or partition files.

---

### Phase 4 — Self-refining (Week 3 convergence)

### [B-HOZ-15] `utility_score` increment

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 4 — Section 3 |
| File | `services/knowledge_base/chroma_adapter.py` |
| Complexity | M |
| Depends On | B-HOZ-07, B-YAH-11 |
| Blocks | B-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Implements Phase 4 increment formulas on `COMPLETED` events.

```math
utility\_score\_{new} = utility\_score\_{old} + (0.1 \times engagement\_quality)
```

```math
engagement\_quality = \frac{engagement\_time}{expected\_time} \times (1 - frustration\_score)
```

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-14** acceptance criteria.

**Approach-Specific Note:** Target Week 3 vs Approach A Week 4.

> ⚠️ **Integration Risk:** Utility writes vs reads during `search`—debounce mandatory.

---

### [B-HOZ-16] Full mutation logic

| Field | Value |
|-------|-------|
| Owner | Hozaifa |
| Phase | Phase 4 — Section 2 |
| File | `services/director/mutation_logic.py` |
| Complexity | L |
| Depends On | B-HOZ-14, B-HOZ-10 |
| Blocks | B-YAH-14 |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-HOZ-15** (Pivot, `interest_profile`, Phase 4 Supabase alignment).

**Acceptance Criteria:**

- [ ] Same as **A-HOZ-15** acceptance criteria.

**Approach-Specific Note:** Bundled into accelerated Week 3; Week 4 reserved for hardening.

---

### [B-YAH-14] Triple-Threat v2

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 4 — Section 3 |
| File | `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | B-HOZ-15, B-YAH-04 |
| Blocks | B-YAH-15 |
| Status | 🔲 Not Started |

**What & Why:** Phase 4 four-term ranking.

```math
Score = (SemanticSimilarity \times 0.35) + (FormWeight \times 0.25) + (R_{app} \times 0.25) + (UtilityScore \times 0.15)
```

**Acceptance Criteria:**

- [ ] Same as **A-YAH-14** acceptance criteria.

**Approach-Specific Note:** Lands Week 3; may race **B-YAH-13** fixes—prefer feature branch behind flag.

---

### [B-YAH-15] 14-day evolution integration test

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 4 — success metric |
| File | `tests/integration/test_roadmap_evolution_14d.py` |
| Complexity | L |
| Depends On | B-YAH-14, B-HOZ-16, B-HOZ-11 |
| Blocks | None |
| Status | 🔲 Not Started |

**What & Why:** Same as **A-YAH-15**.

**Acceptance Criteria:**

- [ ] Same as **A-YAH-15** acceptance criteria.

**Approach-Specific Note:** Week 3 target; Week 4 buffer for flake hardening per Section 5 timeline.

---

## Section 5 — Approach B sprint timeline

### Week summary

| Week | Theme | Hozaifa focus | Yahya focus |
|------|-------|---------------|-------------|
| Week 1 | Contracts + parallel build | B-HOZ-01 → B-HOZ-06 | B-YAH-01 → B-YAH-07 |
| Week 2 | Real swap + Director begins | B-HOZ-07 → B-HOZ-14 | B-YAH-08 → B-YAH-13 |
| Week 3 | Self-refining convergence | B-HOZ-15, B-HOZ-16 | B-YAH-14, B-YAH-15 |
| Week 4 | Buffer + hardening | Integrity audit, perf tuning | Safety regression + E2E polish |

### Week 1 — Contracts + parallel build

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | B-HOZ-01 contract session (schemas + mock + façade) | B-YAH-01 scaffold |
| Tue | B-HOZ-02 contract tests | B-YAH-02 Profiler |
| Wed | B-HOZ-03 PDF utils | B-YAH-03 retrieval |
| Thu | B-HOZ-04 chunker | B-YAH-04 Triple-Threat |
| Fri | B-HOZ-05 formatter start | B-YAH-05 Gamifier, B-YAH-06 Auditor start |

**End-of-Week Gate:** **B-YAH-07** demo green on mock; `pytest tests/contracts/` green.

### Week 2 — Real swap + Director begins

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | B-HOZ-06 finish, B-HOZ-07 real adapter | B-YAH-06 finish, B-YAH-07 polish |
| Tue | B-HOZ-07 tests, B-HOZ-08 integrity | B-YAH-08 swap attempt |
| Wed | B-HOZ-09 migration, B-HOZ-10 Supabase | B-YAH-08 regression fix, B-YAH-09 i18n |
| Thu | B-HOZ-11 state, B-HOZ-12 health | B-YAH-10 E2E real data |
| Fri | B-HOZ-13 evaluator | B-YAH-11 telemetry, B-YAH-12 sentiment |

**End-of-Week Gate:** Contract suite passes on real adapter; telemetry writing to `interaction_logs`.

### Week 3 — Self-refining convergence

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | B-HOZ-14 mutations | B-YAH-13 overrides |
| Tue | B-HOZ-15 utility increment | B-YAH-14 Triple-Threat v2 |
| Wed | B-HOZ-16 mutation_logic | B-YAH-15 simulation start |
| Thu | Supabase Phase 4 alignment | B-YAH-15 assertions |
| Fri | Joint integration checkpoint | Joint integration checkpoint |

**End-of-Week Gate:** Phase 4 success metric test passes or only known flakes documented.

### Week 4 — Buffer + hardening

| Day | Hozaifa | Yahya |
|-----|---------|-------|
| Mon | Chroma perf profiling, batch tuning | Auditor regression matrix |
| Tue | Integrity audits across collections | Client contract tests |
| Wed | Load test `search` p95 | Digital-detox scenario re-run |
| Thu | Documentation + runbooks | Demo rehearsal |
| Fri | Release checklist | Release checklist |

**End-of-Week Gate:** Production readiness sign-off or explicit deferrals logged.

---

## Section 6 — Approach B risk register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Real adapter differs from mock | Medium | High | Expand **B-HOZ-02** with edge cases; require parity checklist before **B-YAH-08** |
| Concurrent `pipeline.py` edits | High | Medium | Serialize **B-YAH-03** then **B-YAH-04**; short PRs |
| Mock seed unrepresentative | Medium | Medium | Day 1 real PDF sample in mock (**Artifact 2** checklist) |
| Agents pass mock, fail real | Medium | High | **B-YAH-08** acceptance: zero contract regressions |
| Schema locked too early | Low | Critical | 30-minute schema review immediately before **B-HOZ-01** merge |
