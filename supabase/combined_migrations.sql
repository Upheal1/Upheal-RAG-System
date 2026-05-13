-- ============================================================
-- Migration: 001_create_interaction_logs.sql
-- ============================================================
-- Migration: 001_create_interaction_logs.sql
-- Description: User interaction telemetry table for tracking task interactions.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-01

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Interaction type enum
CREATE TYPE interaction_type AS ENUM (
    'VIEWED',
    'STARTED',
    'COMPLETED',
    'SKIPPED'
);

-- Main interaction logs table
CREATE TABLE interaction_logs (
    log_id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL,
    task_id         UUID        NOT NULL,
    interaction_type interaction_type NOT NULL,
    completion_time INTEGER     CHECK (completion_time >= 0),
    drop_off_point  DOUBLE PRECISION CHECK (drop_off_point >= 0.0 AND drop_off_point <= 1.0),
    xp_earned      INTEGER     NOT NULL DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (log_id)
);

-- Indexes for common query patterns
CREATE INDEX idx_interaction_logs_user_id ON interaction_logs(user_id);
CREATE INDEX idx_interaction_logs_task_id ON interaction_logs(task_id);
CREATE INDEX idx_interaction_logs_recorded_at ON interaction_logs(recorded_at DESC);
CREATE INDEX idx_interaction_logs_user_recorded ON interaction_logs(user_id, recorded_at DESC);
CREATE INDEX idx_interaction_logs_interaction_type ON interaction_logs(interaction_type);

-- Retention policy comment (optional: set to auto-delete old logs after 90 days)
-- ALTER TABLE interaction_logs SET (
--     timescaledb hypertable,
--     timescaledb.initial_interval = INTERVAL '30 days'
-- );

COMMENT ON TABLE interaction_logs IS 'User interaction telemetry: tracks task views, starts, completions, and skips for Director self-correction analytics.';
COMMENT ON COLUMN interaction_logs.log_id IS 'Primary key, auto-generated UUID';
COMMENT ON COLUMN interaction_logs.user_id IS 'User performing the interaction';
COMMENT ON COLUMN interaction_logs.task_id IS 'Clinical task being interacted with';
COMMENT ON COLUMN interaction_logs.interaction_type IS 'Type of interaction: VIEWED, STARTED, COMPLETED, or SKIPPED';
COMMENT ON COLUMN interaction_logs.completion_time IS 'Seconds spent on the task';
COMMENT ON COLUMN interaction_logs.drop_off_point IS 'Progress through task as fraction 0.0–1.0';
COMMENT ON COLUMN interaction_logs.xp_earned IS 'XP awarded for this interaction';
COMMENT ON COLUMN interaction_logs.recorded_at IS 'Server timestamp of interaction';


-- ============================================================
-- Migration: 002_create_roadmap_mutations.sql
-- ============================================================
-- Migration: 002_create_roadmap_mutations.sql
-- Description: Director mutation audit trail for tracking roadmap changes.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-01

-- Enable UUID extension (if not already created in previous migrations)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Mutation action enum
CREATE TYPE mutation_action AS ENUM (
    'DOWNGRADE_PIVOT',
    'PROMOTION',
    'EMERGENCY_OVERRIDE',
    'RETRIEVAL_REWEIGHT',
    'XP_MULTIPLIER_ADJUST'
);

-- Roadmap mutations audit table
CREATE TABLE roadmap_mutations (
    mutation_id          UUID          NOT NULL DEFAULT gen_random_uuid(),
    user_id             UUID          NOT NULL,
    directive_id        UUID          NOT NULL,
    kind                mutation_action NOT NULL,
    pre_mutation_state  JSONB         NOT NULL,
    post_mutation_state JSONB         NOT NULL,
    retrieval_overrides JSONB,
    rationale           TEXT          NOT NULL,
    triggered_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    valid_from           TIMESTAMPTZ   NOT NULL,
    valid_until         TIMESTAMPTZ,

    PRIMARY KEY (mutation_id)
);

-- Indexes for common query patterns
CREATE INDEX idx_roadmap_mutations_user_id ON roadmap_mutations(user_id);
CREATE INDEX idx_roadmap_mutations_triggered_at ON roadmap_mutations(triggered_at DESC);
CREATE INDEX idx_roadmap_mutations_user_triggered ON roadmap_mutations(user_id, triggered_at DESC);
CREATE INDEX idx_roadmap_mutations_kind ON roadmap_mutations(kind);
CREATE INDEX idx_roadmap_mutations_valid_period ON roadmap_mutations(valid_from, valid_until);

-- GIST index on JSONB for efficient state comparisons
CREATE INDEX idx_roadmap_mutations_pre_state ON roadmap_mutations USING GIN (pre_mutation_state);
CREATE INDEX idx_roadmap_mutations_post_state ON roadmap_mutations USING GIN (post_mutation_state);

COMMENT ON TABLE roadmap_mutations IS 'Director mutation audit trail: records all roadmap modifications issued by the Director self-correction engine.';
COMMENT ON COLUMN roadmap_mutations.mutation_id IS 'Primary key, auto-generated UUID';
COMMENT ON COLUMN roadmap_mutations.user_id IS 'User whose roadmap was mutated';
COMMENT ON COLUMN roadmap_mutations.directive_id IS 'Reference to the Director instruction directive that triggered this mutation';
COMMENT ON COLUMN roadmap_mutations.kind IS 'Type of mutation: DOWNGRADE_PIVOT, PROMOTION, EMERGENCY_OVERRIDE, RETRIEVAL_REWEIGHT, XP_MULTIPLIER_ADJUST';
COMMENT ON COLUMN roadmap_mutations.pre_mutation_state IS 'Snapshot of roadmap state before mutation (difficulty tier, XP values, symptom weights)';
COMMENT ON COLUMN roadmap_mutations.post_mutation_state IS 'Snapshot of roadmap state after mutation';
COMMENT ON COLUMN roadmap_mutations.retrieval_overrides IS 'JSON containing Director retrieval constraints: max_difficulty, xp_multiplier, symptom_tag_weights';
COMMENT ON COLUMN roadmap_mutations.rationale IS 'Director reasoning in plain English';
COMMENT ON COLUMN roadmap_mutations.triggered_at IS 'Server timestamp when mutation was triggered';
COMMENT ON COLUMN roadmap_mutations.valid_from IS 'When the mutation becomes active';
COMMENT ON COLUMN roadmap_mutations.valid_until IS 'When the mutation expires (NULL = permanent until overridden)';


-- ============================================================
-- Migration: 003_create_users_and_profiles.sql
-- ============================================================
-- Migration: 003_create_users_and_profiles.sql
-- Description: Core user tables — users (auth baseline), user_profiles (clinical scores, level, preferences)
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table (auth service baseline, minimal)
CREATE TABLE users (
    id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    email       TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id)
);

CREATE INDEX idx_users_email ON users(email);

-- User clinical profiles
CREATE TABLE user_profiles (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL UNIQUE,
    screen_time_minutes INTEGER     NOT NULL DEFAULT 0,
    gad7_score          INTEGER     NOT NULL DEFAULT 0,
    phq9_score          INTEGER     NOT NULL DEFAULT 0,
    user_level          INTEGER     NOT NULL DEFAULT 1,
    modality_weights    JSONB       NOT NULL DEFAULT '{}',
    tag_boosts          JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_user_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_user_level ON user_profiles(user_level);

COMMENT ON TABLE users IS 'Auth baseline — minimal identity table. Extend with auth provider fields as needed.';
COMMENT ON TABLE user_profiles IS 'Per-user clinical profile: screen time, GAD-7/PHQ-9 scores, difficulty level, modality/tag preferences.';
COMMENT ON COLUMN user_profiles.screen_time_minutes IS 'Daily screen time in minutes';
COMMENT ON COLUMN user_profiles.gad7_score IS 'GAD-7 anxiety score (0–21)';
COMMENT ON COLUMN user_profiles.phq9_score IS 'PHQ-9 depression score (0–27)';
COMMENT ON COLUMN user_profiles.user_level IS 'Gamification difficulty tier (1–5)';
COMMENT ON COLUMN user_profiles.modality_weights IS 'JSON: {breathing: 0.8, journaling: 0.5, ...}';
COMMENT ON COLUMN user_profiles.tag_boosts IS 'JSON: {anxiety: 1.2, depression: 0.9, ...}';


-- ============================================================
-- Migration: 004_create_clinical_tasks.sql
-- ============================================================
-- Migration: 004_create_clinical_tasks.sql
-- Description: Canonical clinical task definitions — the source of truth for Chroma-adjacent metadata
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE task_modality AS ENUM (
    'breathing',
    'journaling',
    'audio_guided',
    'video_guided',
    'cognitive',
    'behavioral',
    'social',
    'physical'
);

CREATE TYPE task_locale AS ENUM (
    'en',
    'ar',
    'bilingual'
);

CREATE TABLE clinical_tasks (
    id              UUID          NOT NULL DEFAULT gen_random_uuid(),
    title           TEXT          NOT NULL,
    description     TEXT          NOT NULL,
    difficulty      INTEGER       NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    xp_reward       INTEGER       NOT NULL DEFAULT 10,
    safety_risk     BOOLEAN       NOT NULL DEFAULT FALSE,
    utility_score   DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    clinical_tags   JSONB         NOT NULL DEFAULT '[]',
    modality        task_modality NOT NULL DEFAULT 'cognitive',
    locale          task_locale   NOT NULL DEFAULT 'en',
    chroma_task_id  UUID,
    metadata        JSONB         NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id)
);

CREATE INDEX idx_clinical_tasks_difficulty ON clinical_tasks(difficulty);
CREATE INDEX idx_clinical_tasks_modality ON clinical_tasks(modality);
CREATE INDEX idx_clinical_tasks_locale ON clinical_tasks(locale);
CREATE INDEX idx_clinical_tasks_safety_risk ON clinical_tasks(safety_risk) WHERE safety_risk = TRUE;
CREATE INDEX idx_clinical_tasks_chroma_task_id ON clinical_tasks(chroma_task_id);
CREATE INDEX idx_clinical_tasks_clinical_tags ON clinical_tasks USING GIN (clinical_tags);

COMMENT ON TABLE clinical_tasks IS 'Canonical clinical task definitions — synced from Chroma enriched metadata as source of truth.';
COMMENT ON COLUMN clinical_tasks.id IS 'Primary key, matches Chroma document ID';
COMMENT ON COLUMN clinical_tasks.title IS 'Human-readable task title';
COMMENT ON COLUMN clinical_tasks.description IS 'Full task description / instructions';
COMMENT ON COLUMN clinical_tasks.difficulty IS 'Difficulty tier 1–5';
COMMENT ON COLUMN clinical_tasks.xp_reward IS 'Base XP reward for task completion';
COMMENT ON COLUMN clinical_tasks.safety_risk IS 'True if task contains crisis content requiring auditor override';
COMMENT ON COLUMN clinical_tasks.utility_score IS 'Adaptive utility score updated on task completion (0.0–1.0)';
COMMENT ON COLUMN clinical_tasks.clinical_tags IS 'JSON array: [anxiety, depression, digital-detox, ...]';
COMMENT ON COLUMN clinical_tasks.modality IS 'Primary modality: breathing, journaling, audio_guided, video_guided, cognitive, behavioral, social, physical';
COMMENT ON COLUMN clinical_tasks.locale IS 'Language: en, ar, bilingual';
COMMENT ON COLUMN clinical_tasks.chroma_task_id IS 'Optional link to Chroma document ID if task was enriched from PDF';
COMMENT ON COLUMN clinical_tasks.metadata IS 'Arbitrary additional metadata JSON blob';


-- ============================================================
-- Migration: 005_create_roadmaps_and_tasks.sql
-- ============================================================
-- Migration: 005_create_roadmaps_and_tasks.sql
-- Description: Roadmap generation records and their line items
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE roadmap_status AS ENUM (
    'ACTIVE',
    'COMPLETED',
    'EXPIRED',
    'SUPERSEDED'
);

CREATE TABLE roadmaps (
    id                  UUID          NOT NULL DEFAULT gen_random_uuid(),
    user_id             UUID          NOT NULL,
    generation_number   INTEGER       NOT NULL DEFAULT 1,
    overall_theme       TEXT,
    status              roadmap_status NOT NULL DEFAULT 'ACTIVE',
    director_overrides  JSONB         NOT NULL DEFAULT '{}',
    generated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    valid_from           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    valid_until         TIMESTAMPTZ,

    PRIMARY KEY (id),
    CONSTRAINT fk_roadmap_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_roadmaps_user_id ON roadmaps(user_id);
CREATE INDEX idx_roadmaps_generation ON roadmaps(user_id, generation_number DESC);
CREATE INDEX idx_roadmaps_valid_period ON roadmaps(valid_from, valid_until);
CREATE INDEX idx_roadmaps_status ON roadmaps(status);

CREATE TABLE roadmap_tasks (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    roadmap_id      UUID        NOT NULL,
    task_id         UUID        NOT NULL,
    sequence_order  INTEGER     NOT NULL DEFAULT 0,
    xp_earned       INTEGER     NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'ASSIGNED',
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,

    PRIMARY KEY (id),
    CONSTRAINT fk_roadmap_task_roadmap FOREIGN KEY (roadmap_id) REFERENCES roadmaps(id) ON DELETE CASCADE,
    CONSTRAINT fk_roadmap_task_task FOREIGN KEY (task_id) REFERENCES clinical_tasks(id) ON DELETE CASCADE
);

CREATE INDEX idx_roadmap_tasks_roadmap_id ON roadmap_tasks(roadmap_id);
CREATE INDEX idx_roadmap_tasks_task_id ON roadmap_tasks(task_id);
CREATE INDEX idx_roadmap_tasks_status ON roadmap_tasks(status);

COMMENT ON TABLE roadmaps IS 'Per-user roadmap generation record with validity window and Director override instructions.';
COMMENT ON COLUMN roadmaps.generation_number IS 'Incrementing generation counter per user (1, 2, 3, ...)';
COMMENT ON COLUMN roadmaps.overall_theme IS 'High-level theme label: anxiety-management, depression-recovery, digital-detox, ...';
COMMENT ON COLUMN roadmaps.status IS 'ACTIVE: in use; COMPLETED: all tasks done; EXPIRED: past valid_until; SUPERSEDED: newer generation exists';
COMMENT ON COLUMN roadmaps.director_overrides IS 'JSON snapshot of Director mutation instructions active during this generation';
COMMENT ON TABLE roadmap_tasks IS 'Line items within a roadmap: task reference, sequence order, XP earned, completion status.';


-- ============================================================
-- Migration: 006_create_assessment_responses.sql
-- ============================================================
-- Migration: 006_create_assessment_responses.sql
-- Description: Raw assessment form submissions (GAD-7, PHQ-9, screen time) per user
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE assessment_responses (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL,
    locale          TEXT        NOT NULL DEFAULT 'en',
    form_payload    JSONB       NOT NULL,
    gad7_score      INTEGER,
    phq9_score      INTEGER,
    screen_time_minutes INTEGER,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_assessment_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_assessment_responses_user_id ON assessment_responses(user_id);
CREATE INDEX idx_assessment_responses_recorded_at ON assessment_responses(user_id, recorded_at DESC);
CREATE INDEX idx_assessment_responses_gad7 ON assessment_responses(gad7_score);
CREATE INDEX idx_assessment_responses_phq9 ON assessment_responses(phq9_score);

COMMENT ON TABLE assessment_responses IS 'Raw assessment form submissions: GAD-7, PHQ-9, screen time. Used by Profiler to compute R_app and keyword weights.';
COMMENT ON COLUMN assessment_responses.form_payload IS 'Full JSON of raw form answers per locale';
COMMENT ON COLUMN assessment_responses.gad7_score IS 'Derived GAD-7 total (0–21)';
COMMENT ON COLUMN assessment_responses.phq9_score IS 'Derived PHQ-9 total (0–27)';
COMMENT ON COLUMN assessment_responses.screen_time_minutes IS 'Derived daily screen time in minutes';


-- ============================================================
-- Migration: 007_create_interest_profiles.sql
-- ============================================================
-- Migration: 007_create_interest_profiles.sql
-- Description: Director's evolving interest/modality profile per user
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE interest_profiles (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id                 UUID        NOT NULL UNIQUE,
    tag_preferences         JSONB       NOT NULL DEFAULT '{}',
    modality_preferences    JSONB       NOT NULL DEFAULT '{}',
    skipped_modalities      JSONB       NOT NULL DEFAULT '[]',
    engagement_quality_avg  DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    frustration_score_avg   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_interest_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_interest_profiles_user_id ON interest_profiles(user_id);
CREATE INDEX idx_interest_profiles_tag_prefs ON interest_profiles USING GIN (tag_preferences);
CREATE INDEX idx_interest_profiles_modality_prefs ON interest_profiles USING GIN (modality_preferences);

COMMENT ON TABLE interest_profiles IS 'Director-evolved interest profile: tag/modality preferences, skipped modalities, engagement quality rolling average.';
COMMENT ON COLUMN interest_profiles.tag_preferences IS 'JSON: {anxiety: 1.2, depression: 0.8, ...} — updated by Director on each mutation cycle';
COMMENT ON COLUMN interest_profiles.modality_preferences IS 'JSON: {breathing: 0.9, journaling: 0.3, audio_guided: 0.7, ...}';
COMMENT ON COLUMN interest_profiles.skipped_modalities IS 'JSON array: modalities user has skipped 2+ times — signals to avoid';
COMMENT ON COLUMN interest_profiles.engagement_quality_avg IS 'Rolling average engagement quality (0.0–1.0) from task completions';
COMMENT ON COLUMN interest_profiles.frustration_score_avg IS 'Rolling average frustration score from chat feedback';


-- ============================================================
-- Migration: 008_add_foreign_keys.sql
-- ============================================================
-- Migration: 008_add_foreign_keys.sql
-- Description: Add foreign key constraints to interaction_logs and roadmap_mutations
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01
-- Note: Run AFTER 001, 002, 003 are applied (FKs need users table to exist first)

-- Add FK to interaction_logs
ALTER TABLE interaction_logs
    ADD CONSTRAINT fk_interaction_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_interaction_logs_task FOREIGN KEY (task_id) REFERENCES clinical_tasks(id) ON DELETE SET NULL;

-- Add FKs to roadmap_mutations
ALTER TABLE roadmap_mutations
    ADD CONSTRAINT fk_roadmap_mutations_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;


-- ============================================================
-- Migration: 009_create_retrieval_logs_and_chat.sql
-- Description: Retrieval logs for Director self-correction, chat history,
--              XP audit ledger, task feedback, and roadmap task status enum.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-09
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. Retrieval logs (Director self-correction)
-- ============================================================
CREATE TABLE retrieval_logs (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL,
    roadmap_id          UUID,
    query_embedding     JSONB       NOT NULL DEFAULT '{}',
    retrieved_task_ids  JSONB       NOT NULL DEFAULT '[]',
    similarity_scores   JSONB       NOT NULL DEFAULT '{}',
    filters_applied     JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_retrieval_user     FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_retrieval_roadmap  FOREIGN KEY (roadmap_id) REFERENCES roadmaps(id) ON DELETE SET NULL
);

CREATE INDEX idx_retrieval_logs_user_id     ON retrieval_logs(user_id);
CREATE INDEX idx_retrieval_logs_roadmap_id  ON retrieval_logs(roadmap_id);
CREATE INDEX idx_retrieval_logs_created_at  ON retrieval_logs(created_at DESC);

COMMENT ON TABLE retrieval_logs IS 'Director self-correction: records what Chroma retrieved, similarity scores, and filters applied per roadmap generation.';
COMMENT ON COLUMN retrieval_logs.query_embedding     IS 'JSON of the query embedding vector sent to Chroma';
COMMENT ON COLUMN retrieval_logs.retrieved_task_ids  IS 'JSON array of clinical_task IDs returned by Chroma';
COMMENT ON COLUMN retrieval_logs.similarity_scores   IS 'JSON map of task_id ? similarity score';
COMMENT ON COLUMN retrieval_logs.filters_applied     IS 'JSON of retrieval filters: difficulty_range, modality, tag_weights, etc.';

-- ============================================================
-- 2. Chat sessions & messages (conversational UI)
-- ============================================================
CREATE TABLE chat_sessions (
    id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL,
    roadmap_id  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_chat_session_user     FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_session_roadmap  FOREIGN KEY (roadmap_id) REFERENCES roadmaps(id) ON DELETE SET NULL
);

CREATE TABLE chat_messages (
    id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL,
    role        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_chat_message_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    CONSTRAINT chk_chat_role CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_chat_sessions_user_id    ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_roadmap_id ON chat_sessions(roadmap_id);
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(session_id, created_at DESC);

COMMENT ON TABLE chat_sessions  IS 'Conversational session grouping for LLM chat.';
COMMENT ON TABLE chat_messages  IS 'Individual messages within a chat session.';

-- ============================================================
-- 3. Roadmap task status enum + migration
-- ============================================================
CREATE TYPE roadmap_task_status AS ENUM (
    'ASSIGNED',
    'IN_PROGRESS',
    'COMPLETED',
    'SKIPPED',
    'DROPPED'
);

-- Must drop default first, then cast, then re-add default
ALTER TABLE roadmap_tasks
    ALTER COLUMN status DROP DEFAULT,
    ALTER COLUMN status TYPE roadmap_task_status
    USING status::roadmap_task_status,
    ALTER COLUMN status SET DEFAULT 'ASSIGNED';

-- ============================================================
-- 4. Remove redundancy in user_profiles (keep static clinical snapshot)
-- ============================================================
ALTER TABLE user_profiles DROP COLUMN IF EXISTS modality_weights;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS tag_boosts;

-- ============================================================
-- 5. XP transaction ledger (gamification audit)
-- ============================================================
CREATE TABLE xp_transactions (
    id           UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id      UUID        NOT NULL,
    amount       INTEGER     NOT NULL,
    source       TEXT        NOT NULL,
    reference_id UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id),
    CONSTRAINT fk_xp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_xp_source CHECK (source IN ('task_completion', 'streak_bonus', 'director_adjustment'))
);

CREATE INDEX idx_xp_transactions_user_id ON xp_transactions(user_id);
CREATE INDEX idx_xp_transactions_created_at ON xp_transactions(user_id, created_at DESC);

COMMENT ON TABLE xp_transactions IS 'Gamification audit ledger: every XP change traced back to a source event.';

-- ============================================================
-- 6. Interaction logs: qualitative feedback columns
-- ============================================================
ALTER TABLE interaction_logs
    ADD COLUMN user_rating   INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    ADD COLUMN feedback_text TEXT;

COMMENT ON COLUMN interaction_logs.user_rating   IS 'User-provided 1�5 rating for the task';
COMMENT ON COLUMN interaction_logs.feedback_text IS 'Optional free-text feedback explaining rating or experience';


-- ============================================================
-- Migration: 010_add_data_retention_cleanup.sql
-- Description: Manual cleanup functions + optional pg_cron jobs
--              for log tables (interaction_logs, chat_messages,
--              retrieval_logs, assessment_responses).
--              NOTE: pg_cron may be limited on free tier.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-09
-- ============================================================

-- ============================================================
-- 1. Retention settings table (configurable per log type)
-- ============================================================
CREATE TABLE IF NOT EXISTS retention_settings (
    log_type        TEXT PRIMARY KEY,
    retention_days  INTEGER NOT NULL DEFAULT 30,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    rows_deleted    INTEGER DEFAULT 0
);

INSERT INTO retention_settings (log_type, retention_days, enabled) VALUES
    ('interaction_logs',   90, TRUE),
    ('chat_messages',      30, TRUE),
    ('retrieval_logs',     14, TRUE),
    ('assessment_responses', 365, TRUE)
ON CONFLICT (log_type) DO NOTHING;

COMMENT ON TABLE retention_settings IS 'Configurable retention policy for log tables. Modify retention_days to adjust how long logs are kept.';

-- ============================================================
-- 2. Cleanup functions (can be called via Supabase Edge Function or pg_cron)
-- ============================================================

CREATE OR REPLACE FUNCTION cleanup_interaction_logs()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'interaction_logs' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM interaction_logs
            WHERE recorded_at < NOW() - (days || ' days')::INTERVAL
            RETURNING log_id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'interaction_logs';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION cleanup_chat_messages()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'chat_messages' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM chat_messages
            WHERE created_at < NOW() - (days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'chat_messages';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION cleanup_retrieval_logs()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'retrieval_logs' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM retrieval_logs
            WHERE created_at < NOW() - (days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'retrieval_logs';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION cleanup_assessment_responses()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'assessment_responses' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM assessment_responses
            WHERE recorded_at < NOW() - (days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'assessment_responses';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 3. Master cleanup function
-- ============================================================
CREATE OR REPLACE FUNCTION run_all_cleanup()
RETURNS TABLE (log_type TEXT, deleted_count INTEGER) AS $$
BEGIN
    RETURN QUERY SELECT 'interaction_logs'::TEXT, cleanup_interaction_logs();
    RETURN QUERY SELECT 'chat_messages'::TEXT, cleanup_chat_messages();
    RETURN QUERY SELECT 'retrieval_logs'::TEXT, cleanup_retrieval_logs();
    RETURN QUERY SELECT 'assessment_responses'::TEXT, cleanup_assessment_responses();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 4. Optional: pg_cron scheduled jobs (may not work on free tier)
-- ============================================================
-- Uncomment below if pg_cron is enabled on your project.
-- Free tier: cron jobs may be disabled; use Edge Function or
-- external scheduler to call run_all_cleanup() instead.

-- CREATE EXTENSION IF NOT EXISTS pg_cron;
--
-- SELECT cron.schedule('cleanup-logs-daily', '0 2 * * *',
--     'SELECT run_all_cleanup()');

COMMENT ON FUNCTION cleanup_interaction_logs IS 'Deletes interaction_logs older than retention_settings.retention_days. Call manually or via scheduler.';
COMMENT ON FUNCTION run_all_cleanup IS 'Runs all cleanup functions. Returns rows deleted per log_type. Call via: SELECT * FROM run_all_cleanup();';

-- ============================================================
-- 5. Row count estimate view (for monitoring)
-- ============================================================
CREATE OR REPLACE VIEW log_table_sizes AS
SELECT
    relname AS table_name,
    n_live_tup AS row_count_estimate,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE relname IN ('interaction_logs', 'chat_messages', 'retrieval_logs', 'assessment_responses', 'xp_transactions')
ORDER BY pg_total_relation_size(relid) DESC;


-- ============================================================
-- Migration: 011_fix_security_definer_functions.sql
-- Description: Fix SECURITY DEFINER functions exposed via REST API
--              by revoking anon/authenticated execute permissions.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-09
-- ============================================================

-- ============================================================
-- Fix: rls_auto_enable() SECURITY DEFINER exposed to anon/authenticated
-- ============================================================
-- This function is callable by anon and authenticated roles via /rest/v1/rpc.
-- Since it's SECURITY DEFINER, it runs with owner privileges.
-- Fix: revoke execute from public roles. Keep it for admin/service only.

-- Only revoke if function exists (may not exist in fresh local databases)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'rls_auto_enable'
    ) THEN
        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM authenticated';
    END IF;
END $$;

-- Alternative: if the function is not needed at all, drop it:
-- DROP FUNCTION IF EXISTS public.rls_auto_enable();

-- If you need the function but it should be SECURITY INVOKER instead:
-- ALTER FUNCTION public.rls_auto_enable() SECURITY INVOKER;

-- If you need a helper to list all SECURITY DEFINER functions in public schema:
CREATE OR REPLACE FUNCTION public.list_security_definer_functions()
RETURNS TABLE (schema_name TEXT, function_name TEXT, arguments TEXT, exposed_roles TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.nspname::TEXT AS schema_name,
        p.proname::TEXT AS function_name,
        pg_get_function_arguments(p.oid)::TEXT AS arguments,
        COALESCE(
            (SELECT string_agg(r.rolname, ', ')
             FROM pg_proc p2
             CROSS JOIN LATERAL aclexplode(p2.proacl) acl
             JOIN pg_roles r ON r.oid = acl.grantee
             WHERE p2.oid = p.oid
               AND acl.privilege_type = 'EXECUTE'
               AND r.rolname IN ('anon', 'authenticated')),
            ''
        ) AS exposed_roles
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.prosecdef = TRUE
      AND n.nspname = 'public'
    ORDER BY p.proname;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Note: list_security_definer_functions is also SECURITY DEFINER,
-- but it only reads system catalogs and doesn't modify data.
-- If you want it accessible via API, keep it; otherwise revoke too:
-- REVOKE EXECUTE ON FUNCTION public.list_security_definer_functions() FROM anon, authenticated;


-- ============================================================
-- Migration: 012_enable_rls_policies.sql
-- Description: Enable RLS on all user-facing tables with proper policies
-- Owner: Yehia
-- Created: 2026-05-12
-- ============================================================

-- Enable RLS on all user-facing tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_mutations ENABLE ROW LEVEL SECURITY;
ALTER TABLE interest_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrieval_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE xp_transactions ENABLE ROW LEVEL SECURITY;

-- clinical_tasks: read-only for authenticated users
ALTER TABLE clinical_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read clinical_tasks"
  ON clinical_tasks FOR SELECT
  TO authenticated
  USING (true);

-- retention_settings: service role only (no anon/authenticated access)
ALTER TABLE retention_settings ENABLE ROW LEVEL SECURITY;

-- Users table: read/update own row only
CREATE POLICY "Users can read own row"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own row"
  ON users FOR UPDATE
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can insert own row"
  ON users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

-- user_profiles: own profile only
CREATE POLICY "Users can read own profile"
  ON user_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile"
  ON user_profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- assessment_responses: own responses only
CREATE POLICY "Users can read own assessments"
  ON assessment_responses FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own assessments"
  ON assessment_responses FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmaps: own roadmaps only
CREATE POLICY "Users can read own roadmaps"
  ON roadmaps FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own roadmaps"
  ON roadmaps FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmap_tasks: access via roadmap ownership
CREATE POLICY "Users can access roadmap tasks"
  ON roadmap_tasks FOR ALL
  TO authenticated
  USING (
    roadmap_id IN (
      SELECT id FROM roadmaps WHERE user_id = auth.uid()
    )
  );

-- interest_profiles: own profile only
CREATE POLICY "Users can access own interest profile"
  ON interest_profiles FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);

-- chat_sessions: own sessions only
CREATE POLICY "Users can access own chat sessions"
  ON chat_sessions FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);

-- chat_messages: access via session ownership
CREATE POLICY "Users can access chat messages"
  ON chat_messages FOR ALL
  TO authenticated
  USING (
    session_id IN (
      SELECT id FROM chat_sessions WHERE user_id = auth.uid()
    )
  );

-- interaction_logs: own logs only
CREATE POLICY "Users can read own interaction logs"
  ON interaction_logs FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own interaction logs"
  ON interaction_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- xp_transactions: own transactions only
CREATE POLICY "Users can read own XP transactions"
  ON xp_transactions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

-- retrieval_logs: own logs only
CREATE POLICY "Users can insert own retrieval logs"
  ON retrieval_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmap_mutations: own mutations only
CREATE POLICY "Users can access own roadmap mutations"
  ON roadmap_mutations FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);


-- ============================================================
-- Migration: 013_roadmap_ninety_day.sql
-- ============================================================
-- Migration: 013_roadmap_ninety_day.sql
-- Description: Add 90-day roadmap columns + auto-create user profile on Supabase Auth signup
-- Part of: Deployment Task Plan — Phase 2E
-- Created: 2026-05-13

-- ============================================================
-- 1. Extend roadmaps table for 90-day tracking
-- ============================================================

ALTER TABLE roadmaps
    ADD COLUMN IF NOT EXISTS total_days INT NOT NULL DEFAULT 90,
    ADD COLUMN IF NOT EXISTS current_day INT NOT NULL DEFAULT 1;

COMMENT ON COLUMN roadmaps.total_days IS 'Total days in the roadmap cycle (default 90)';
COMMENT ON COLUMN roadmaps.current_day IS 'Current day within the roadmap cycle (1–90)';

-- ============================================================
-- 2. Auto-create public.users + public.user_profiles on signup
-- ============================================================
-- When Supabase Auth creates a user in auth.users, this trigger
-- mirrors the row into public.users and creates an empty profile.
-- This satisfies the FK constraints used by all downstream tables.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Mirror into public.users (our app-level user table)
    INSERT INTO public.users (id, email, created_at, updated_at)
    VALUES (new.id, new.email, now(), now())
    ON CONFLICT (id) DO NOTHING;

    -- Create empty clinical profile
    INSERT INTO public.user_profiles (user_id, created_at, updated_at)
    VALUES (new.id, now(), now())
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if present (idempotent)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Create trigger: runs AFTER INSERT on auth.users
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

COMMENT ON FUNCTION public.handle_new_user() IS
    'Auto-provisions public.users and public.user_profiles when a new Supabase Auth user signs up.';


