#!/usr/bin/env bash
# ============================================================
# UpHeal Deployment Script — Task 5C: Run Supabase Migrations
# ============================================================
# Usage:
#   export SUPABASE_DB_URL="postgresql://postgres:[password]@db.gcxxmjptbyvlabqzcprv.supabase.co:5432/postgres"
#   ./scripts/run_migrations.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$REPO_ROOT/supabase/migrations"

# Allow override via env var
SUPABASE_DB_URL="${SUPABASE_DB_URL:-}"

if [ -z "$SUPABASE_DB_URL" ]; then
    echo "ERROR: SUPABASE_DB_URL is not set."
    echo ""
    echo "Get your database URL from Supabase Dashboard → Project Settings → Database:"
    echo "  Connection string → URI (use the Session Pooler or Transaction Pooler)"
    echo ""
    echo "Example:"
    echo '  export SUPABASE_DB_URL="postgresql://postgres:[password]@db.gcxxmjptbyvlabqzcprv.supabase.co:5432/postgres"'
    echo ""
    exit 1
fi

echo "=============================================="
echo "  UpHeal Supabase Migration Runner"
echo "=============================================="
echo ""
echo "Target: $SUPABASE_DB_URL"
echo ""

# Check required tools
if ! command -v psql &> /dev/null; then
    echo "ERROR: psql (PostgreSQL client) is not installed."
    echo "Install it: https://www.postgresql.org/download/"
    exit 1
fi

# Verify connection
echo "→ Testing database connection..."
if ! psql "$SUPABASE_DB_URL" -c "SELECT version();" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to database. Check SUPABASE_DB_URL."
    exit 1
fi
echo "  ✓ Connection successful"
echo ""

# Define migrations in order
# Note: 001-011 should already be applied. We run them idempotently (IF NOT EXISTS).
# 012 and 013 are the new ones needed for deployment.

MIGRATIONS=(
    "012_enable_rls_policies.sql"
    "013_roadmap_ninety_day.sql"
)

echo "→ Running migrations..."
echo ""

for mig in "${MIGRATIONS[@]}"; do
    filepath="$MIGRATIONS_DIR/$mig"
    if [ ! -f "$filepath" ]; then
        echo "  ✗ MISSING: $mig"
        exit 1
    fi

    echo "  → Applying $mig ..."
    if psql "$SUPABASE_DB_URL" -f "$filepath" > /tmp/migration_$mig.log 2>&1; then
        echo "    ✓ $mig applied successfully"
    else
        echo "    ✗ $mig FAILED"
        echo ""
        echo "--- Error output ---"
        cat /tmp/migration_$mig.log
        echo "--------------------"
        exit 1
    fi
done

echo ""
echo "=============================================="
echo "  ✓ All migrations applied successfully!"
echo "=============================================="
echo ""

# Verify
echo "→ Verification:"
echo ""
echo "  1. Checking roadmaps table columns..."
psql "$SUPABASE_DB_URL" -c "
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'roadmaps'
    AND column_name IN ('total_days', 'current_day');
" | grep -E "total_days|current_day" | sed 's/^/    /'

echo ""
echo "  2. Checking handle_new_user trigger..."
psql "$SUPABASE_DB_URL" -c "
    SELECT trigger_name, event_manipulation, action_statement
    FROM information_schema.triggers
    WHERE trigger_name = 'on_auth_user_created';
" | grep -E "on_auth_user_created|INSERT" | sed 's/^/    /'

echo ""
echo "=============================================="
echo "  Migration 5C Complete!"
echo "=============================================="
echo ""
echo "Next step: 5D — Deploy to Railway"
echo "  railway up"
echo ""
