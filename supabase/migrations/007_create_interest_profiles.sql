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
