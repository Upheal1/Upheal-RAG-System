-- Migration: 003_create_users_and_profiles.sql
-- Description: Core user tables — users (auth baseline), user_profiles (clinical scores, level, preferences)
-- Part of: A-HOZ-10 Supabase Migrations — expanded schema
-- Created: 2026-05-01

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (auth service baseline, minimal)
CREATE TABLE users (
    id          UUID        NOT NULL DEFAULT uuid_generate_v4(),
    email       TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id)
);

CREATE INDEX idx_users_email ON users(email);

-- User clinical profiles
CREATE TABLE user_profiles (
    id                  UUID        NOT NULL DEFAULT uuid_generate_v4(),
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
