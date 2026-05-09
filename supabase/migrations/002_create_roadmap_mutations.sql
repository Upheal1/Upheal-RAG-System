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
