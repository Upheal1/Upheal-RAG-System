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
COMMENT ON COLUMN retrieval_logs.similarity_scores   IS 'JSON map of task_id → similarity score';
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

COMMENT ON COLUMN interaction_logs.user_rating   IS 'User-provided 1–5 rating for the task';
COMMENT ON COLUMN interaction_logs.feedback_text IS 'Optional free-text feedback explaining rating or experience';
