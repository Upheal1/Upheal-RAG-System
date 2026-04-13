# Implementation Tracking

Tracks progress on Approach A (Foundation-First) implementation tasks.

## Team Roles

| Role | Focus | Owner |
|------|-------|-------|
| **Hozaifa** | Data Layer | Knowledge Infrastructure (Phase 1 + Supabase) |
| **Yahya** | Agent Layer | Guild → Director → Self-Refining (Phase 2-4) |

## Phase 1 — Knowledge Infrastructure

### Hozaifa Tasks

| Task | Name | Status | PR | Notes |
|------|------|--------|-----|-------|
| A-HOZ-01 | Pydantic schemas | ✅ Done | - | In `main` (commit 362f70e) |
| A-HOZ-02 | Structured JSON logger | ✅ Done | [#5](https://github.com/Upheal1/Upheal-RAG-System/pull/5) | |
| A-HOZ-03 | PDF extraction and noise filter | 🔲 Pending | - | |
| A-HOZ-04 | Semantic chunker (15% overlap) | 🔲 Pending | - | |
| A-HOZ-05 | Formatter Agent (LLM integration) | 🔲 Pending | - | |
| A-HOZ-06 | **GATE** ChromaDB hybrid adapter | 🔲 Pending | - | Unlocks Yahya's real retrieval |
| A-HOZ-07 | Integrity check script | 🔲 Pending | - | |
| A-HOZ-08 | GET /health for knowledge base | 🔲 Pending | - | |
| A-HOZ-09 | Initial clinical PDF migration script | 🔲 Pending | - | |
| A-HOZ-10 | Supabase migrations | 🔲 Pending | - | interaction_logs, roadmap_mutations |
| A-HOZ-11 | State manager (pathing + Supabase sync) | 🔲 Pending | - | |

### Yahya Tasks (Phase 1-2 scaffolding)

| Task | Name | Status | PR | Notes |
|------|------|--------|-----|-------|
| A-YAH-01 | FastAPI scaffold | ✅ Done | - | In `main` |
| A-YAH-02 | Profiler Agent | ✅ Done | - | In `main` |
| A-YAH-03 | ClinicalTask fixtures | 🔲 Pending | - | |
| A-YAH-04 | Knowledge retrieval (real adapter) | 🔲 Pending | - | After A-HOZ-06 |
| A-YAH-05 | Triple-Threat reranking | 🔲 Pending | - | |
| A-YAH-06 | Gamifier Agent (XP + sequencing) | 🔲 Pending | - | |
| A-YAH-07 | Clinical Auditor | ✅ Done | - | In `main` |
| A-YAH-08 | Arabic + English i18n | 🔲 Pending | - | |
| A-YAH-09 | Full orchestration chain | 🔲 Pending | - | |
| A-YAH-10 | POST /api/roadmap | 🔲 Pending | - | |

## Phase 2 — The Guild

### Hozaifa Tasks (continued)

| Task | Name | Status | PR | Notes |
|------|------|--------|-----|-------|
| A-HOZ-10 | Supabase migrations | 🔲 Pending | - | (moved to Phase 2) |
| A-HOZ-11 | State manager | 🔲 Pending | - | |

### Yahya Tasks

| Task | Name | Status | PR | Notes |
|------|------|--------|-----|-------|
| A-YAH-04 | Knowledge retrieval | 🔲 Pending | - | After A-HOZ-06 |
| A-YAH-05 | Triple-Threat reranking | 🔲 Pending | - | |
| A-YAH-06 | Gamifier Agent | 🔲 Pending | - | |
| A-YAH-07 | Clinical Auditor | ✅ Done | - | |
| A-YAH-08 | i18n constants | 🔲 Pending | - | |
| A-YAH-09 | Full orchestration chain | 🔲 Pending | - | |
| A-YAH-10 | POST /api/roadmap | 🔲 Pending | - | |

## Phase 3 — The Director

| Task | Owner | Status | PR | Notes |
|------|-------|--------|-----|-------|
| A-HOZ-12 | Hozaifa | 🔲 Pending | - | Director evaluator |
| A-HOZ-13 | Hozaifa | 🔲 Pending | - | Mutation engine |
| A-YAH-11 | Yahya | 🔲 Pending | - | POST /api/telemetry |
| A-YAH-12 | Yahya | 🔲 Pending | - | Sentiment hook |
| A-YAH-13 | Yahya | 🔲 Pending | - | Director override in pipeline |

## Phase 4 — Self-Refining Loop

| Task | Owner | Status | PR | Notes |
|------|-------|--------|-----|-------|
| A-HOZ-14 | Hozaifa | 🔲 Pending | - | utility_score increment |
| A-HOZ-15 | Hozaifa | 🔲 Pending | - | Mutation logic + interest_profile |
| A-YAH-14 | Yahya | 🔲 Pending | - | Triple-Threat v2 |
| A-YAH-15 | Yahya | 🔲 Pending | - | 14-day E2E simulation |

## Sprint Timeline

```
Week 1: Factory Floor
├── Hozaifa: A-HOZ-01 → A-HOZ-06
└── Yahya: A-YAH-01, A-YAH-02, A-YAH-03

Week 2: The Guild
├── Hozaifa: A-HOZ-07 → A-HOZ-11
└── Yahya: A-YAH-04 → A-YAH-10

Week 3: The Director
├── Hozaifa: A-HOZ-12, A-HOZ-13
└── Yahya: A-YAH-11 → A-YAH-13

Week 4: Self-Refining
├── Hozaifa: A-HOZ-14, A-HOZ-15
└── Yahya: A-YAH-14, A-YAH-15
```

## Legend

| Symbol | Meaning |
|--------|---------|
| 🔲 Not Started | Task not yet started |
| 🔄 In Progress | Task currently being implemented |
| ✅ Done | Task completed and merged |
| 🚧 Blocked | Task blocked by dependency |
| ⚠️ At Risk | Task may slip |
