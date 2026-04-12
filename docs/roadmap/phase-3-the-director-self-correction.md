# Phase 3 — The Director: Self-Correction

## Overview

Phase 3 adds **The Director**, an autonomous supervisory layer that ingests quantitative telemetry and qualitative signals, evaluates whether the user is engaging and improving, and issues **mutation instructions** to the Architect when plans must change. The system remains clinically bounded: mutations adjust difficulty bands, XP incentives, and retrieval focus—not unsupervised therapy content generation.

## Architecture Diagram

```
Flutter / client
      │
      │ POST /api/telemetry
      ▼
services/gateway/main.py ─────────────────────┐
      │                                        │
      │                              (persist)
      ▼                                        ▼
interaction_logs (Supabase)          roadmap_mutations (Supabase)
      │                                        ▲
      │                                        │
      └──────────────► services/director/evaluator.py
                       (cron / every 5 completions)
                                │
                                ▼
                       services/director/mutation_engine.py
                                │
                                │ DirectorOverride JSON
                                ▼
                       services/architect/pipeline.py
                       (retrieval constraints + time window)

Optional qualitative path:
services/architect/auditor.py ──► frustration_score ──► Director (AMBER)
```

## Detailed Specifications

### Section 1 — Interaction data stream

#### 1.1 `services/gateway/main.py` — Quantitative telemetry

**New endpoint:** `POST /api/telemetry`

**Payload schema**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `UUID` | Which task was interacted with |
| `interaction_type` | `str` | `VIEWED` \| `STARTED` \| `COMPLETED` \| `SKIPPED` |
| `completion_time` | `int` | Seconds spent on task |
| `drop_off_point` | `float` | 0.0–1.0, progress through the task |
| `xp_earned` | `int` | Actual XP awarded |

Rows append to **`interaction_logs`** (see Technical Deliverables) with `user_id` and server timestamp.

#### 1.2 `services/architect/auditor.py` — Qualitative sentiment hook

- When **chat feedback** (or free-text reaction) is available, run a **lightweight sentiment / frustration classifier** (small model or rules + lexicon, version-pinned).
- **Output:** `frustration_score` ∈ \([0, 1]\) where `0` is calm and `1` is highly frustrated.
- **Threshold:** `frustration_score > 0.7` sets an **AMBER** advisory flag to the Director on the next evaluation cycle (does not alone replace crisis RED handling from Phase 2).

> ⚠️ **Safety Note:** Sentiment hooks must not block crisis detection; RED pathways from Phase 2 remain authoritative for self-harm language.

---

### Section 2 — The Director Agent (`services/director/`)

#### 2.1 `services/director/evaluator.py` — Performance audit

**Schedule:** every **7 days** (CRON) **or** after **5** task completions since last audit (whichever comes first per user).

**Computed metrics**

| Metric | Formula | Threshold |
|--------|---------|-----------|
| Engagement Rate | `completed / assigned` (windowed) | Failure if `< 0.40` |
| Clinical Velocity | Rate of difficulty tier progression | Failure if stuck ≥ 5 days on same tier |
| Sentiment Trend | Rolling average `frustration_score` (7d) | Failure if `> 0.70` |

**Output:** `PerformanceReport` object (Pydantic or dataclass) containing user id, window bounds, metric values, boolean `failure_flags`, and human-readable `summary`.

#### 2.2 `services/director/mutation_engine.py` — Mutation triggers

**Downgrade pivot**

- **Trigger:** `engagement_rate < 0.40` **OR** `frustration_score > 0.70` (latest rolling).
- **Action:** Instruct Architect to restrict retrieval to **`difficulty ≤ 2`** for **48 hours**; apply **`xp_reward` multiplier +20%** on assigned tasks.

**Director instruction (structured object example)**

```json
{
  "directive_id": "uuid",
  "user_id": "uuid",
  "kind": "DOWNGRADE_PIVOT",
  "valid_from": "2026-04-11T00:00:00Z",
  "valid_until": "2026-04-13T00:00:00Z",
  "retrieval": {
    "max_difficulty": 2,
    "xp_multiplier": 1.2
  },
  "rationale": "Engagement below threshold; reduce load and increase reward density."
}
```

**Promotion**

- **Trigger:** `engagement_rate = 1.0` for **3 consecutive days** (all assigned tasks completed).
- **Action:** Unlock **`difficulty` 4–5** tasks; shift retrieval priority from **“Crisis Management”** toward **“Resilience Building”** by updating primary `symptom_tags` / keyword weights in the `RetrievalQuery` synthesis step.

Persist each mutation to **`roadmap_mutations`** with before/after snapshots.

---

### Section 3 — Mutation log (Supabase)

**Table: `roadmap_mutations`**

| Column | Type | Description |
|--------|------|-------------|
| `mutation_id` | `UUID` | Unique mutation record |
| `user_id` | `UUID` | Affected user |
| `pre_mutation_state` | `JSONB` | Snapshot of roadmap scores / tier before change |
| `rationale` | `text` | Director’s reasoning in plain English |
| `action` | `text` | What was changed |
| `triggered_at` | `timestamp` | When the mutation occurred |

**Table: `interaction_logs`** (telemetry backing store)

| Column | Type | Description |
|--------|------|-------------|
| `log_id` | `UUID` | Primary key |
| `user_id` | `UUID` | User |
| `task_id` | `UUID` | Task |
| `interaction_type` | `text` | Enum string |
| `completion_time` | `int` | Seconds |
| `drop_off_point` | `float` | 0–1 |
| `xp_earned` | `int` | XP |
| `recorded_at` | `timestamp` | Server time |

---

## Technical Deliverables

- [ ] `supabase/migrations/YYYYMMDDHHMMSS_interaction_logs.sql` — create `interaction_logs` table.
- [ ] `supabase/migrations/YYYYMMDDHHMMSS_roadmap_mutations.sql` — create `roadmap_mutations` table.
- [ ] `services/gateway/main.py` — `POST /api/telemetry` endpoint implemented.
- [ ] `services/director/evaluator.py` — log aggregation and `PerformanceReport` object implemented.
- [ ] `services/director/mutation_engine.py` — Downgrade and Promotion mutation policies implemented.
- [ ] `services/architect/pipeline.py` — updated to accept Director override instructions before running retrieval.
- [ ] `services/architect/auditor.py` — sentiment classifier hook and `frustration_score` output implemented.

## Success Metric

> **Dynamic adaptation**: In a simulation where a user ignores 3 consecutive “Journaling” tasks, the Director must autonomously refactor the next roadmap to replace “Journaling” with “Audio-Guided Breathing” while maintaining the same clinical goals.

## File Map

```
supabase/migrations/YYYYMMDDHHMMSS_interaction_logs.sql    # Telemetry table DDL
supabase/migrations/YYYYMMDDHHMMSS_roadmap_mutations.sql   # Mutation audit table DDL
services/gateway/main.py                                    # POST /api/telemetry + auth hooks
services/director/__init__.py                               # Package marker (if new)
services/director/evaluator.py                              # Metrics + PerformanceReport
services/director/mutation_engine.py                      # Downgrade / Promotion policies
services/architect/pipeline.py                              # Director override-aware retrieval
services/architect/auditor.py                             # frustration_score emission
```
