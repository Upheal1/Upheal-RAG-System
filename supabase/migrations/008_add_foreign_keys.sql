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
