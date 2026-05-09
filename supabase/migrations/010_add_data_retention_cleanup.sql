-- ============================================================
-- Migration: 010_add_data_retention_cleanup.sql
-- Description: Manual cleanup functions + optional pg_cron jobs
--              for log tables (interaction_logs, chat_messages,
--              retrieval_logs, assessment_responses).
--              NOTE: pg_cron may be limited on free tier.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-09
-- ============================================================

-- ============================================================
-- 1. Retention settings table (configurable per log type)
-- ============================================================
CREATE TABLE IF NOT EXISTS retention_settings (
    log_type        TEXT PRIMARY KEY,
    retention_days  INTEGER NOT NULL DEFAULT 30,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    rows_deleted    INTEGER DEFAULT 0
);

INSERT INTO retention_settings (log_type, retention_days, enabled) VALUES
    ('interaction_logs',   90, TRUE),
    ('chat_messages',      30, TRUE),
    ('retrieval_logs',     14, TRUE),
    ('assessment_responses', 365, TRUE)
ON CONFLICT (log_type) DO NOTHING;

COMMENT ON TABLE retention_settings IS 'Configurable retention policy for log tables. Modify retention_days to adjust how long logs are kept.';

-- ============================================================
-- 2. Cleanup functions (can be called via Supabase Edge Function or pg_cron)
-- ============================================================

CREATE OR REPLACE FUNCTION cleanup_interaction_logs()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'interaction_logs' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM interaction_logs
            WHERE recorded_at < NOW() - (days || ' days')::INTERVAL
            RETURNING log_id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'interaction_logs';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION cleanup_chat_messages()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'chat_messages' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM chat_messages
            WHERE created_at < NOW() - (days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'chat_messages';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION cleanup_retrieval_logs()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'retrieval_logs' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM retrieval_logs
            WHERE created_at < NOW() - (days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'retrieval_logs';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION cleanup_assessment_responses()
RETURNS TABLE (deleted_count INTEGER) AS $$
DECLARE
    days INT;
BEGIN
    SELECT retention_days INTO days
    FROM retention_settings
    WHERE log_type = 'assessment_responses' AND enabled = TRUE;

    IF FOUND THEN
        WITH deleted AS (
            DELETE FROM assessment_responses
            WHERE recorded_at < NOW() - (days || ' days')::INTERVAL
            RETURNING id
        )
        SELECT COUNT(*)::INT INTO deleted_count FROM deleted;

        UPDATE retention_settings
        SET last_run_at = NOW(), rows_deleted = deleted_count
        WHERE log_type = 'assessment_responses';

        RETURN QUERY SELECT deleted_count;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 3. Master cleanup function
-- ============================================================
CREATE OR REPLACE FUNCTION run_all_cleanup()
RETURNS TABLE (log_type TEXT, deleted_count INTEGER) AS $$
BEGIN
    RETURN QUERY SELECT 'interaction_logs'::TEXT, cleanup_interaction_logs();
    RETURN QUERY SELECT 'chat_messages'::TEXT, cleanup_chat_messages();
    RETURN QUERY SELECT 'retrieval_logs'::TEXT, cleanup_retrieval_logs();
    RETURN QUERY SELECT 'assessment_responses'::TEXT, cleanup_assessment_responses();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 4. Optional: pg_cron scheduled jobs (may not work on free tier)
-- ============================================================
-- Uncomment below if pg_cron is enabled on your project.
-- Free tier: cron jobs may be disabled; use Edge Function or
-- external scheduler to call run_all_cleanup() instead.

-- CREATE EXTENSION IF NOT EXISTS pg_cron;
--
-- SELECT cron.schedule('cleanup-logs-daily', '0 2 * * *',
--     'SELECT run_all_cleanup()');

COMMENT ON FUNCTION cleanup_interaction_logs IS 'Deletes interaction_logs older than retention_settings.retention_days. Call manually or via scheduler.';
COMMENT ON FUNCTION run_all_cleanup IS 'Runs all cleanup functions. Returns rows deleted per log_type. Call via: SELECT * FROM run_all_cleanup();';

-- ============================================================
-- 5. Row count estimate view (for monitoring)
-- ============================================================
CREATE OR REPLACE VIEW log_table_sizes AS
SELECT
    relname AS table_name,
    n_live_tup AS row_count_estimate,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE relname IN ('interaction_logs', 'chat_messages', 'retrieval_logs', 'assessment_responses', 'xp_transactions')
ORDER BY pg_total_relation_size(relid) DESC;
