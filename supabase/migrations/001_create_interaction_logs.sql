-- Migration: 001_create_interaction_logs.sql
-- Description: User interaction telemetry table for tracking task interactions.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-01

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Interaction type enum
CREATE TYPE interaction_type AS ENUM (
    'VIEWED',
    'STARTED',
    'COMPLETED',
    'SKIPPED'
);

-- Main interaction logs table
CREATE TABLE interaction_logs (
    log_id          UUID        NOT NULL DEFAULT uuid_generate_v4(),
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
