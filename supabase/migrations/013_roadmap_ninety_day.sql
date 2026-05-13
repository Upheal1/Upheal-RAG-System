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
