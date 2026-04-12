# Phase 4 — Self-Refining Loop

## Overview

Phase 4 evolves The Director from reactive course corrections into a **reflective** system that learns from aggregate outcomes: persistence in Supabase, richer audits, **interest profiles** that reshape ranking, and **utility scores** on chunks so the knowledge base favours content that users actually complete with quality engagement. The Guild’s retrieval formula gains a fourth term tied to proven utility.

## Architecture Diagram

```
Client / Flutter
      │
      │ telemetry + progress sync
      ▼
services/gateway/main.py
      │
      ├──────────────────────────────► Supabase: user_interactions
      │
services/shared/state.py ◄──────────► optimistic locking + retries
      │
      ▼
services/director/evaluator.py
  Compliance · Clinical Velocity · Dopamine Balance
      │
      ▼
services/director/mutation_logic.py
  Downgrade · Pivot + interest_profile persistence
      │
      ├──────────────► Supabase: user profile / interest_profile
      │
      ▼
services/architect/pipeline.py
  Triple-Threat v2 (includes UtilityScore) + active mutations
      │
      ▼
services/knowledge_base/chroma_adapter.py
  utility_score increment on COMPLETED (batched / debounced writes)
```

## Detailed Specifications

### Section 1 — Persistent interaction engine (Supabase)

#### 1.1 Telemetry schema

**Table: `user_interactions`**

| Column | Type | Description |
|--------|------|-------------|
| `interaction_id` | `UUID` | Primary key |
| `user_id` | `UUID` | FK to users |
| `task_id` | `UUID` | FK to clinical task |
| `interaction_type` | `str` | `VIEWED` \| `STARTED` \| `COMPLETED` \| `SKIPPED` |
| `engagement_time` | `int` | Total seconds |
| `feedback_sentiment` | `float` | 0.0–1.0 from emoji-react or chat |
| `recorded_at` | `timestamp` | UTC timestamp |

> ⚠️ **Safety Note:** Store minimum PHI; prefer opaque ids and aggregate analytics for model training boundaries per your IRB / DPA.

#### 1.2 `services/shared/state.py` — State manager

- **Sync** local Flutter progress to Supabase using idempotent row keys (`user_id`, `task_id`, `session_id`).
- **Optimistic locking:** include `version` or `updated_at` on user progress rows; on conflict, client merges and retries with backoff.
- **Offline retry:** queue events locally; exponential backoff on sync (e.g. 1s, 2s, 4s, cap 60s); drop duplicates via `interaction_id` / client-generated UUID.

---

### Section 2 — The Director Agent (full build)

#### 2.1 `services/director/evaluator.py` — Clinical performance audit

**Full metrics suite**

| Metric | Definition |
|--------|------------|
| Compliance Rate | Percentage of assigned tasks completed in the window |
| Clinical Velocity | Week-over-week change in normalised GAD-7/PHQ-9 (from reassessments) |
| Dopamine Balance | `XP earned / XP potential` over the window — proxy for reward sufficiency |

Outputs feed `mutation_logic` with the same hard safety precedence as Phase 3.

#### 2.2 `services/director/mutation_logic.py` — Full mutation suite

**Downgrade policy:** Force Architect to **Level 1–2** difficulty band for **48h** to rebuild confidence (same spirit as Phase 3, may merge policies).

**Pivot policy:** If modality `JOURNALING` is repeatedly **SKIPPED** but `BREATHING` tasks are **COMPLETED**, update **`interest_profile`** to add **+0.3** weight to `"Physical Exercises"` (or equivalent tag bucket) inside the **Triple-Threat** `FormWeight` channel until the next weekly audit.

**Persistent object: `interest_profile`** (Supabase JSONB column on `user_preferences` or dedicated table)

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `UUID` | Owner |
| `modality_weights` | `dict` | Map modality key → additive weight delta (e.g. `{"JOURNALING": -0.2, "BREATHING": 0.3}`) |
| `tag_boosts` | `dict` | Map clinical tag → multiplier contribution for FormWeight |
| `updated_at` | `timestamp` | Last mutation |
| `version` | `int` | Optimistic concurrency |

---

### Section 3 — Self-refining knowledge base

Every time a `ClinicalTask` is marked **`COMPLETED`** by any user, its **`utility_score`** in Chroma metadata should be incremented (implementation: debounced batch updates to avoid write storms).

**Increment formula**

```math
utility\_score\_{new} = utility\_score\_{old} + (0.1 \times engagement\_quality)
```

**Engagement quality**

```math
engagement\_quality = \frac{engagement\_time}{expected\_time} \times (1 - frustration\_score)
```

**Triple-Threat v2 (Phase 4)**

```math
Score = (SemanticSimilarity \times 0.35) + (FormWeight \times 0.25) + (R_{app} \times 0.25) + (UtilityScore \times 0.15)
```

**Interpretation:** Proven, well-completed chunks rise relative to raw theoretical passages; `UtilityScore` should be normalised to \([0,1]\) before applying the weight.

> ⚠️ **Safety Note:** Utility learning must not promote crisis or unreviewed content; only tasks passing formatter + auditor rules participate, and RED pathways bypass ranking games.

---

## Technical Deliverables

- [ ] `supabase/migrations/YYYYMMDDHHMMSS_user_interactions.sql` — deploy `user_interactions` table.
- [ ] `supabase/migrations/YYYYMMDDHHMMSS_roadmap_mutations_phase4.sql` — ensure `roadmap_mutations` aligns with Phase 4 columns if extended.
- [ ] `services/gateway/main.py` — `POST /api/telemetry` fully implemented with `interaction_type` enum validation.
- [ ] `services/director/evaluator.py` — weekly audit logic with Compliance Rate, Clinical Velocity, and Dopamine Balance metrics.
- [ ] `services/director/mutation_logic.py` — Downgrade and Pivot policies with `interest_profile` persistence.
- [ ] `services/architect/pipeline.py` — updated to check for active Director mutations before retrieval and to apply Triple-Threat v2.
- [ ] `services/knowledge_base/chroma_adapter.py` — `utility_score` increment logic on task completion (debounced/batched).
- [ ] `services/shared/state.py` — optimistic locking and offline retry for progress sync (extended from Phase 1).

## Success Metric

> **The evolution check**: Within 14 days of use, the system must show a statistically significant difference between a user’s first generated roadmap and their third — proving the Director has shifted the difficulty, content type, or clinical tone based on that specific user’s performance logs.

## File Map

```
supabase/migrations/YYYYMMDDHHMMSS_user_interactions.sql   # Interaction history DDL
supabase/migrations/YYYYMMDDHHMMSS_roadmap_mutations_phase4.sql  # Optional alignment/extension
services/gateway/main.py                                    # Telemetry validation + routing
services/director/evaluator.py                              # Extended audit metrics (weekly)
services/director/mutation_logic.py                         # Pivot + interest_profile + policies
services/architect/pipeline.py                              # Triple-Threat v2 + mutation awareness
services/knowledge_base/chroma_adapter.py                  # utility_score updates on completion
services/shared/state.py                                    # Sync, locks, offline retry
```
