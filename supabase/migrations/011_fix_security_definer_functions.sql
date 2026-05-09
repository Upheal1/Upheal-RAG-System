-- ============================================================
-- Migration: 011_fix_security_definer_functions.sql
-- Description: Fix SECURITY DEFINER functions exposed via REST API
--              by revoking anon/authenticated execute permissions.
-- Part of: A-HOZ-10 Supabase Migrations
-- Created: 2026-05-09
-- ============================================================

-- ============================================================
-- Fix: rls_auto_enable() SECURITY DEFINER exposed to anon/authenticated
-- ============================================================
-- This function is callable by anon and authenticated roles via /rest/v1/rpc.
-- Since it's SECURITY DEFINER, it runs with owner privileges.
-- Fix: revoke execute from public roles. Keep it for admin/service only.

-- Only revoke if function exists (may not exist in fresh local databases)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'rls_auto_enable'
    ) THEN
        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM authenticated';
    END IF;
END $$;

-- Alternative: if the function is not needed at all, drop it:
-- DROP FUNCTION IF EXISTS public.rls_auto_enable();

-- If you need the function but it should be SECURITY INVOKER instead:
-- ALTER FUNCTION public.rls_auto_enable() SECURITY INVOKER;

-- If you need a helper to list all SECURITY DEFINER functions in public schema:
CREATE OR REPLACE FUNCTION public.list_security_definer_functions()
RETURNS TABLE (schema_name TEXT, function_name TEXT, arguments TEXT, exposed_roles TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.nspname::TEXT AS schema_name,
        p.proname::TEXT AS function_name,
        pg_get_function_arguments(p.oid)::TEXT AS arguments,
        COALESCE(
            (SELECT string_agg(r.rolname, ', ')
             FROM pg_proc p2
             CROSS JOIN LATERAL aclexplode(p2.proacl) acl
             JOIN pg_roles r ON r.oid = acl.grantee
             WHERE p2.oid = p.oid
               AND acl.privilege_type = 'EXECUTE'
               AND r.rolname IN ('anon', 'authenticated')),
            ''
        ) AS exposed_roles
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.prosecdef = TRUE
      AND n.nspname = 'public'
    ORDER BY p.proname;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Note: list_security_definer_functions is also SECURITY DEFINER,
-- but it only reads system catalogs and doesn't modify data.
-- If you want it accessible via API, keep it; otherwise revoke too:
-- REVOKE EXECUTE ON FUNCTION public.list_security_definer_functions() FROM anon, authenticated;
