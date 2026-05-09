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
