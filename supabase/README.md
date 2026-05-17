# Supabase Migrations

SQL migrations for Upheal's Supabase PostgreSQL instance. Apply in order (prefix = sequence).

## Migration Order

| # | File | Description |
|---|------|-------------|
| 001 | `001_create_interaction_logs.sql` | User interaction telemetry |
| 002 | `002_create_roadmap_mutations.sql` | Director mutation audit trail |
| 003 | `003_create_users_and_profiles.sql` | Users + user_profiles |
| 004 | `004_create_clinical_tasks.sql` | Canonical task definitions |
| 005 | `005_create_roadmaps_and_tasks.sql` | Roadmaps + roadmap_tasks |
| 006 | `006_create_assessment_responses.sql` | Raw form submissions |
| 007 | `007_create_interest_profiles.sql` | Director interest profiles |
| 008 | `008_add_foreign_keys.sql` | FK constraints on existing tables |
| 009 | `009_create_retrieval_logs_and_chat.sql` | Retrieval logs + chat tables |
| 010 | `010_add_data_retention_cleanup.sql` | Data retention policies |
| 011 | `011_fix_security_definer_functions.sql` | Fix security definer exposure |
| 012 | `012_enable_rls_policies.sql` | Enable RLS on all tables |
| 013 | `013_roadmap_ninety_day.sql` | 90-day roadmap columns + auth signup trigger |

## Schema Map

```mermaid
erDiagram
    users ||--|| user_profiles : "1:1"
    users ||--o{ assessment_responses : "1:N"
    users ||--o{ roadmaps : "1:N"
    users ||--o{ interaction_logs : "1:N"
    users ||--o{ roadmap_mutations : "1:N"
    users ||--o{ interest_profiles : "1:N"
    roadmaps ||--o{ roadmap_tasks : "1:N"
    clinical_tasks ||--o{ roadmap_tasks : "1:N"
    clinical_tasks ||--o{ interaction_logs : "1:N"
```

## Table Reference

### `users`
Auth baseline. Minimal — extend with provider fields as needed.
- `id` (PK), `email` (UNIQUE), `created_at`, `updated_at`

### `user_profiles`
Per-user clinical profile for Profiler + Gamifier.
- `screen_time_minutes`, `gad7_score` (0–21), `phq9_score` (0–27), `user_level` (1–5)
- `modality_weights` (JSON): `{breathing: 0.8, journaling: 0.5, ...}`
- `tag_boosts` (JSON): `{anxiety: 1.2, depression: 0.9, ...}`

### `assessment_responses`
Raw form submissions from client (EN/AR GAD-7, PHQ-9, screen time).
- `form_payload` (JSONB), derived scores, `recorded_at`

### `clinical_tasks`
Canonical task definitions — synced with Chroma metadata as source of truth.
- `title`, `description`, `difficulty` (1–5), `xp_reward`, `safety_risk`, `utility_score`
- `clinical_tags` (JSONB array), `modality`, `locale`, `chroma_task_id`

### `roadmaps`
Per-user roadmap generation record with validity window.
- `user_id`, `generation_number`, `overall_theme`, `status`
- `total_days` (default 90), `current_day` (1–90)
- `director_overrides` (JSON): active mutation instructions snapshot
- `valid_from` / `valid_until`

### `roadmap_tasks`
Line items within a roadmap.
- `roadmap_id`, `task_id`, `sequence_order`, `xp_earned`, `status`
- `assigned_at`, `completed_at`

### `interaction_logs`
User telemetry for Director self-correction.
- `task_id`, `interaction_type` (VIEWED/STARTED/COMPLETED/SKIPPED)
- `completion_time` (seconds), `drop_off_point` (0–1), `xp_earned`

### `roadmap_mutations`
Director mutation audit trail.
- `user_id`, `directive_id`, `kind` (DOWNGRADE_PIVOT/PROMOTION/etc.)
- `pre_mutation_state` / `post_mutation_state` (JSONB snapshots)
- `retrieval_overrides` (JSON), `rationale`, `valid_from` / `valid_until`

### `interest_profiles`
Director-evolved preferences per user.
- `tag_preferences`, `modality_preferences` (JSON)
- `skipped_modalities` (JSON array — 2+ skips → avoid signal)
- `engagement_quality_avg`, `frustration_score_avg`

## Running Migrations

```bash
supabase db push
```

Or via raw SQL:

```bash
psql $SUPABASE_DB_URL -f migrations/001_create_interaction_logs.sql
psql $SUPABASE_DB_URL -f migrations/002_create_roadmap_mutations.sql
# ... etc
```

## Environment Variables

```
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
SUPABASE_PROJECT_REF=your_project_ref
```
