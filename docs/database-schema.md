# Database Schema

> Canonical database schema for the Upheal RAG system.
> Cloud project: `https://gcxxmjptbyvlabqzcprv.supabase.co`

---

## Table of Contents

1. [Architecture](#architecture)
2. [Tables](#tables)
3. [Enums](#enums)
4. [Migration History](#migration-history)
5. [Data Retention](#data-retention)
6. [Security Hardening](#security-hardening)
7. [RAG Flow Mapping](#rag-flow-mapping)
8. [Free Tier Considerations](#free-tier-considerations)
9. [Setup Guide](#setup-guide)

---

## Architecture

![Entity-Relationship Diagram](images/schema-er-diagram.png)

*Full ER diagram showing all 14 tables, their columns, and foreign key relationships.*

```mermaid
flowchart LR
    subgraph "Auth Layer"
        U[users]
    end
    subgraph "Clinical Core"
        CT[clinical_tasks]
        UP[user_profiles]
        IP[interest_profiles]
        AR[assessment_responses]
    end
    subgraph "Roadmap System"
        R[roadmaps]
        RT[roadmap_tasks]
        RM[roadmap_mutations]
    end
    subgraph "Analytics & Telemetry"
        IL[interaction_logs]
        RL[retrieval_logs]
        CS[chat_sessions]
        CM[chat_messages]
        XT[xp_transactions]
    end
    U --> UP
    U --> IP
    U --> AR
    U --> R
    U --> IL
    U --> XT
    R --> RT
    RT --> CT
    IL --> CT
    R --> RL
    R --> CS
    CS --> CM
    RM --> U
```

---

## Tables

### `users` (Auth baseline)

Minimal identity table. Extend with auth provider fields as needed.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `email` | `TEXT` | NOT NULL, UNIQUE | User email |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Registration timestamp |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Last update timestamp |

**Indexes:** `idx_users_email`

---

### `user_profiles` (Static clinical snapshot)

Per-user clinical profile. Stores static assessment-derived scores. Dynamic preferences live in `interest_profiles`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, UNIQUE, FK → `users.id` | Reference to user |
| `screen_time_minutes` | `INTEGER` | NOT NULL, DEFAULT 0 | Daily screen time |
| `gad7_score` | `INTEGER` | NOT NULL, DEFAULT 0 | GAD-7 anxiety score (0–21) |
| `phq9_score` | `INTEGER` | NOT NULL, DEFAULT 0 | PHQ-9 depression score (0–27) |
| `user_level` | `INTEGER` | NOT NULL, DEFAULT 1 | Gamification difficulty tier (1–5) |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Last update timestamp |

**Indexes:** `idx_user_profiles_user_id`, `idx_user_profiles_user_level`

**Note:** `modality_weights` and `tag_boosts` were removed from this table to eliminate redundancy with `interest_profiles` (see Migration 009).

---

### `clinical_tasks` (Canonical task definitions)

Source of truth for Chroma-adjacent metadata. Tasks synced from enriched PDF chunks.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key (matches Chroma doc ID) |
| `title` | `TEXT` | NOT NULL | Human-readable title |
| `description` | `TEXT` | NOT NULL | Full instructions |
| `difficulty` | `INTEGER` | NOT NULL, CHECK 1–5 | Difficulty tier |
| `xp_reward` | `INTEGER` | NOT NULL, DEFAULT 10 | Base XP reward |
| `safety_risk` | `BOOLEAN` | NOT NULL, DEFAULT FALSE | Crisis content flag |
| `utility_score` | `DOUBLE PRECISION` | NOT NULL, DEFAULT 0.5 | Adaptive utility (0.0–1.0) |
| `clinical_tags` | `JSONB` | NOT NULL, DEFAULT `'[]'` | Tags: `anxiety`, `depression`, etc. |
| `modality` | `task_modality` | NOT NULL, DEFAULT `'cognitive'` | Primary modality |
| `locale` | `task_locale` | NOT NULL, DEFAULT `'en'` | Language |
| `chroma_task_id` | `UUID` | — | Link to Chroma document |
| `metadata` | `JSONB` | NOT NULL, DEFAULT `'{}'` | Additional metadata |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Creation timestamp |

**Indexes:** `difficulty`, `modality`, `locale`, `safety_risk` (partial), `chroma_task_id`, `clinical_tags` (GIN)

---

### `roadmaps` (Per-user roadmap generations)

Tracks roadmap versions with validity windows.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | Reference to user |
| `generation_number` | `INTEGER` | NOT NULL, DEFAULT 1 | Incrementing version counter |
| `overall_theme` | `TEXT` | — | Theme label (e.g., `anxiety-management`) |
| `status` | `roadmap_status` | NOT NULL, DEFAULT `'ACTIVE'` | ACTIVE, COMPLETED, EXPIRED, SUPERSEDED |
| `director_overrides` | `JSONB` | NOT NULL, DEFAULT `'{}'` | Director mutation snapshot |
| `generated_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Generation timestamp |
| `valid_from` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()` | Validity start |
| `valid_until` | `TIMESTAMPTZ` | — | Validity end (NULL = permanent) |

**Indexes:** `user_id`, `user_id + generation_number DESC`, `valid_from + valid_until`, `status`

---

### `roadmap_tasks` (Roadmap line items)

Links tasks to roadmaps with sequence and status tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `roadmap_id` | `UUID` | NOT NULL, FK → `roadmaps.id` | Reference to roadmap |
| `task_id` | `UUID` | NOT NULL, FK → `clinical_tasks.id` | Reference to task |
| `sequence_order` | `INTEGER` | NOT NULL, DEFAULT 0 | Task sequence |
| `xp_earned` | `INTEGER` | NOT NULL, DEFAULT 0 | XP earned for completion |
| `status` | `roadmap_task_status` | NOT NULL, DEFAULT `'ASSIGNED'` | ASSIGNED, IN_PROGRESS, COMPLETED, SKIPPED, DROPPED |
| `assigned_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Assignment timestamp |
| `completed_at` | `TIMESTAMPTZ` | — | Completion timestamp |

**Indexes:** `roadmap_id`, `task_id`, `status`

---

### `interaction_logs` (User interaction telemetry)

Tracks task views, starts, completions, and skips for Director self-correction analytics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `log_id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | User |
| `task_id` | `UUID` | NOT NULL, FK → `clinical_tasks.id` | Task |
| `interaction_type` | `interaction_type` | NOT NULL | VIEWED, STARTED, COMPLETED, SKIPPED |
| `completion_time` | `INTEGER` | CHECK ≥ 0 | Seconds spent |
| `drop_off_point` | `DOUBLE PRECISION` | CHECK 0.0–1.0 | Progress fraction |
| `xp_earned` | `INTEGER` | NOT NULL, DEFAULT 0 | XP awarded |
| `recorded_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |
| `user_rating` | `INTEGER` | CHECK 1–5 | Qualitative rating (added in 009) |
| `feedback_text` | `TEXT` | — | Free-text feedback (added in 009) |

**Indexes:** `user_id`, `task_id`, `recorded_at DESC`, `user_id + recorded_at DESC`, `interaction_type`

---

### `roadmap_mutations` (Director mutation audit trail)

Records all roadmap modifications issued by the Director self-correction engine.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `mutation_id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | Affected user |
| `directive_id` | `UUID` | NOT NULL | Triggering directive |
| `kind` | `mutation_action` | NOT NULL | DOWNGRADE_PIVOT, PROMOTION, EMERGENCY_OVERRIDE, RETRIEVAL_REWEIGHT, XP_MULTIPLIER_ADJUST |
| `pre_mutation_state` | `JSONB` | NOT NULL | Before snapshot |
| `post_mutation_state` | `JSONB` | NOT NULL | After snapshot |
| `retrieval_overrides` | `JSONB` | — | Director retrieval constraints |
| `rationale` | `TEXT` | NOT NULL | Director reasoning |
| `triggered_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Trigger timestamp |
| `valid_from` | `TIMESTAMPTZ` | NOT NULL | Activation time |
| `valid_until` | `TIMESTAMPTZ` | — | Expiration (NULL = permanent) |

**Indexes:** `user_id`, `triggered_at DESC`, `user_id + triggered_at DESC`, `kind`, `valid_from + valid_until`, `pre_mutation_state` (GIN), `post_mutation_state` (GIN)

---

### `assessment_responses` (Raw assessment submissions)

GAD-7, PHQ-9, screen time. Used by Profiler to compute R_app and keyword weights.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | User |
| `locale` | `TEXT` | NOT NULL, DEFAULT `'en'` | Language |
| `form_payload` | `JSONB` | NOT NULL | Raw form answers |
| `gad7_score` | `INTEGER` | — | Derived total (0–21) |
| `phq9_score` | `INTEGER` | — | Derived total (0–27) |
| `screen_time_minutes` | `INTEGER` | — | Derived daily screen time |
| `recorded_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |

**Indexes:** `user_id`, `user_id + recorded_at DESC`, `gad7_score`, `phq9_score`

---

### `interest_profiles` (Director-evolved preferences)

Dynamic interest/modality profile per user. Updated by Director on each mutation cycle.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, UNIQUE, FK → `users.id` | User |
| `tag_preferences` | `JSONB` | NOT NULL, DEFAULT `'{}'` | `{anxiety: 1.2, ...}` |
| `modality_preferences` | `JSONB` | NOT NULL, DEFAULT `'{}'` | `{breathing: 0.9, ...}` |
| `skipped_modalities` | `JSONB` | NOT NULL, DEFAULT `'[]'` | Modalities skipped 2+ times |
| `engagement_quality_avg` | `DOUBLE PRECISION` | NOT NULL, DEFAULT 0.5 | Rolling average (0.0–1.0) |
| `frustration_score_avg` | `DOUBLE PRECISION` | NOT NULL, DEFAULT 0.0 | Rolling frustration average |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Last update |

**Indexes:** `user_id`, `tag_preferences` (GIN), `modality_preferences` (GIN)

---

### `retrieval_logs` (Director self-correction)

Records what Chroma retrieved per roadmap generation. Critical for Director self-correction.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | User |
| `roadmap_id` | `UUID` | FK → `roadmaps.id` | Associated roadmap |
| `query_embedding` | `JSONB` | NOT NULL, DEFAULT `'{}'` | Embedding vector |
| `retrieved_task_ids` | `JSONB` | NOT NULL, DEFAULT `'[]'` | Returned task IDs |
| `similarity_scores` | `JSONB` | NOT NULL, DEFAULT `'{}'` | Task ID → score map |
| `filters_applied` | `JSONB` | NOT NULL, DEFAULT `'{}'` | Retrieval filters used |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |

**Indexes:** `user_id`, `roadmap_id`, `created_at DESC`

---

### `chat_sessions` (Conversational session grouping)

Groups LLM chat messages per user/roadmap.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | User |
| `roadmap_id` | `UUID` | FK → `roadmaps.id` | Optional roadmap link |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |

**Indexes:** `user_id`, `roadmap_id`

---

### `chat_messages` (Individual chat messages)

Stores individual LLM chat messages.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `session_id` | `UUID` | NOT NULL, FK → `chat_sessions.id` | Parent session |
| `role` | `TEXT` | NOT NULL, CHECK `('user', 'assistant', 'system')` | Message role |
| `content` | `TEXT` | NOT NULL | Message content |
| `metadata` | `JSONB` | NOT NULL, DEFAULT `'{}'` | Additional metadata |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |

**Indexes:** `session_id`, `session_id + created_at DESC`

---

### `xp_transactions` (Gamification audit ledger)

Every XP change traced back to a source event.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, DEFAULT `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` | User |
| `amount` | `INTEGER` | NOT NULL | XP change (positive/negative) |
| `source` | `TEXT` | NOT NULL, CHECK `('task_completion', 'streak_bonus', 'director_adjustment')` | Source category |
| `reference_id` | `UUID` | — | Optional reference (task, mutation, etc.) |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |

**Indexes:** `user_id`, `user_id + created_at DESC`

---

### `retention_settings` (Configurable cleanup policy)

Controls data retention for log tables.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `log_type` | `TEXT` | PK | Table name |
| `retention_days` | `INTEGER` | NOT NULL, DEFAULT 30 | Days to keep |
| `enabled` | `BOOLEAN` | NOT NULL, DEFAULT TRUE | Cleanup enabled |
| `last_run_at` | `TIMESTAMPTZ` | — | Last cleanup run |
| `rows_deleted` | `INTEGER` | DEFAULT 0 | Total rows deleted |

**Default values:**

| log_type | retention_days |
|----------|----------------|
| interaction_logs | 90 |
| chat_messages | 30 |
| retrieval_logs | 14 |
| assessment_responses | 365 |

---

### `log_table_sizes` (Monitoring view)

Row count and size estimates for log tables.

```sql
SELECT * FROM log_table_sizes;
```

---

## Enums

| Enum | Values |
|------|--------|
| `interaction_type` | VIEWED, STARTED, COMPLETED, SKIPPED |
| `mutation_action` | DOWNGRADE_PIVOT, PROMOTION, EMERGENCY_OVERRIDE, RETRIEVAL_REWEIGHT, XP_MULTIPLIER_ADJUST |
| `roadmap_status` | ACTIVE, COMPLETED, EXPIRED, SUPERSEDED |
| `roadmap_task_status` | ASSIGNED, IN_PROGRESS, COMPLETED, SKIPPED, DROPPED |
| `task_modality` | breathing, journaling, audio_guided, video_guided, cognitive, behavioral, social, physical |
| `task_locale` | en, ar, bilingual |

---

## Migration History

| # | File | Description | Date |
|---|------|-------------|------|
| 001 | `001_create_interaction_logs.sql` | User interaction telemetry | 2026-05-01 |
| 002 | `002_create_roadmap_mutations.sql` | Director mutation audit trail | 2026-05-01 |
| 003 | `003_create_users_and_profiles.sql` | Core user tables | 2026-05-01 |
| 004 | `004_create_clinical_tasks.sql` | Canonical task definitions | 2026-05-01 |
| 005 | `005_create_roadmaps_and_tasks.sql` | Roadmap generation and line items | 2026-05-01 |
| 006 | `006_create_assessment_responses.sql` | Assessment form submissions | 2026-05-01 |
| 007 | `007_create_interest_profiles.sql` | Evolving interest profiles | 2026-05-01 |
| 008 | `008_add_foreign_keys.sql` | Foreign key constraints | 2026-05-01 |
| 009 | `009_create_retrieval_logs_and_chat.sql` | Retrieval logs, chat history, XP ledger, feedback columns, enum fix, redundancy removal | 2026-05-09 |
| 010 | `010_add_data_retention_cleanup.sql` | Cleanup functions, retention settings, monitoring view | 2026-05-09 |
| 011 | `011_fix_security_definer_functions.sql` | Security hardening for exposed SECURITY DEFINER functions | 2026-05-09 |

---

## Data Retention

### Cleanup Functions

```sql
-- Run all cleanup jobs at once
SELECT * FROM run_all_cleanup();

-- Or run individually
SELECT * FROM cleanup_interaction_logs();
SELECT * FROM cleanup_chat_messages();
SELECT * FROM cleanup_retrieval_logs();
SELECT * FROM cleanup_assessment_responses();
```

### Adjust Retention

```sql
-- Reduce chat retention to 7 days
UPDATE retention_settings 
SET retention_days = 7 
WHERE log_type = 'chat_messages';

-- Disable cleanup for a table
UPDATE retention_settings 
SET enabled = FALSE 
WHERE log_type = 'assessment_responses';
```

---

## Security Hardening

### Security Linter Findings Fixed

| Issue | Fix |
|-------|-----|
| `anon` can execute `SECURITY DEFINER` function | Revoked `EXECUTE` from `anon` |
| `authenticated` can execute `SECURITY DEFINER` function | Revoked `EXECUTE` from `authenticated` |

### Audit Helper

```sql
-- List all SECURITY DEFINER functions and their exposed roles
SELECT * FROM list_security_definer_functions();
```

### Security Best Practices

1. **Don't connect MCP to production** — Use dev/staging only
2. **Enable read-only mode** if connecting to real data: `https://mcp.supabase.com/mcp?read_only=true`
3. **Scope MCP to project**: `https://mcp.supabase.com/mcp?project_ref=gcxxmjptbyvlabqzcprv`
4. **Always review tool calls** before executing in MCP clients

---

## RAG Flow Mapping

### Director → Profiler → Retriever → Generator

| RAG Component | Database Tables |
|---------------|-----------------|
| **Profiler** | `assessment_responses`, `user_profiles`, `interest_profiles` |
| **Director** | `interaction_logs`, `roadmap_mutations`, `retrieval_logs`, `interest_profiles` |
| **Retriever** | `clinical_tasks`, `interest_profiles`, `retrieval_logs` |
| **Generator** | `roadmaps`, `roadmap_tasks`, `clinical_tasks`, `chat_sessions`, `chat_messages` |
| **Telemetry** | `interaction_logs`, `xp_transactions` |

---

## Free Tier Considerations

| Limit | Free Plan | Strategy |
|-------|-----------|----------|
| Database size | 500 MB | Cleanup functions control growth; `interaction_logs` and `chat_messages` are highest risk |
| Egress | 5 GB/month | Fine for dev/testing |
| Auto-pause | After 1 week | Use `supabase start` for active dev; keep cloud for staging only |
| Backups | None | Export regularly: `supabase db dump -f backup.sql` |
| Log retention | 1 day | Use application-level logging for debugging |

**Recommendation:** Use **local Supabase** (`supabase start`) for active development. Reserve the cloud project for staging and demos.

---

## Setup Guide

### Local Development

```bash
# Install Supabase CLI
npm install supabase --save-dev

# Start local instance
npx supabase start

# Push migrations
npx supabase db push
```

### Connect to Cloud Project

```bash
# Login
npx supabase login

# Link to project
npx supabase link --project-ref gcxxmjptbyvlabqzcprv

# Push migrations
npx supabase db push
```

### Database Connection

| Environment | URL |
|-------------|-----|
| Local | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| Cloud | `https://gcxxmjptbyvlabqzcprv.supabase.co` |
| REST API | `https://gcxxmjptbyvlabqzcprv.supabase.co/rest/v1` |
| MCP | `http://localhost:54321/mcp` |

---

## Changelog

| Date | Change | Migration |
|------|--------|-----------|
| 2026-05-01 | Initial schema (8 migrations) | 001–008 |
| 2026-05-09 | Added retrieval logs, chat tables, XP ledger, task feedback, roadmap status enum | 009 |
| 2026-05-09 | Removed `modality_weights` and `tag_boosts` from `user_profiles` (redundancy fix) | 009 |
| 2026-05-09 | Added data retention cleanup functions and monitoring view | 010 |
| 2026-05-09 | Fixed SECURITY DEFINER function exposure | 011 |
