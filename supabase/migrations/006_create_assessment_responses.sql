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
