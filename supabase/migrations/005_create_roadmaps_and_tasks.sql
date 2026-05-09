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
