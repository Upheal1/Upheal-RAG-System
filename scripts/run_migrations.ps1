#Requires -Version 5.1
<#
.SYNOPSIS
    UpHeal Deployment Script — Task 5C: Run Supabase Migrations

.DESCRIPTION
    Applies migrations 012 and 013 to the Supabase PostgreSQL database.
    Requires the SUPABASE_DB_URL environment variable to be set.

.EXAMPLE
    $env:SUPABASE_DB_URL = "postgresql://postgres:[password]@db.gcxxmjptbyvlabqzcprv.supabase.co:5432/postgres"
    .\scripts\run_migrations.ps1

.NOTES
    Get your DB URL from Supabase Dashboard → Project Settings → Database → Connection string
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptDir
$migrationsDir = Join-Path $repoRoot "supabase\migrations"

# Check env var
$supabaseDbUrl = $env:SUPABASE_DB_URL
if (-not $supabaseDbUrl) {
    Write-Host "ERROR: SUPABASE_DB_URL is not set." -ForegroundColor Red
    Write-Host ""
    Write-Host "Get your database URL from Supabase Dashboard → Project Settings → Database"
    Write-Host ""
    Write-Host "Example:"
    Write-Host '  $env:SUPABASE_DB_URL = "postgresql://postgres:[password]@db.gcxxmjptbyvlabqzcprv.supabase.co:5432/postgres"' -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  UpHeal Supabase Migration Runner" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Target: $supabaseDbUrl"
Write-Host ""

# Check psql
$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    Write-Host "ERROR: psql (PostgreSQL client) is not installed." -ForegroundColor Red
    Write-Host "Download: https://www.postgresql.org/download/"
    exit 1
}

# Test connection
Write-Host "→ Testing database connection..."
try {
    $null = & psql $supabaseDbUrl -c "SELECT version();" 2>$null
    Write-Host "  ✓ Connection successful" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Cannot connect to database. Check SUPABASE_DB_URL." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Define migrations
$migrations = @(
    "012_enable_rls_policies.sql"
    "013_roadmap_ninety_day.sql"
)

Write-Host "→ Running migrations..." -ForegroundColor Yellow
Write-Host ""

foreach ($mig in $migrations) {
    $filepath = Join-Path $migrationsDir $mig
    if (-not (Test-Path $filepath)) {
        Write-Host "  ✗ MISSING: $mig" -ForegroundColor Red
        exit 1
    }

    Write-Host "  → Applying $mig ..."
    $logFile = [System.IO.Path]::GetTempFileName()

    & psql $supabaseDbUrl -f "$filepath" > "$logFile" 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "    ✓ $mig applied successfully" -ForegroundColor Green
        Remove-Item $logFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "    ✗ $mig FAILED (exit $exitCode)" -ForegroundColor Red
        Write-Host ""
        Write-Host "--- Error output ---" -ForegroundColor Red
        Get-Content $logFile | ForEach-Object { Write-Host "    $_" }
        Write-Host "--------------------" -ForegroundColor Red
        Remove-Item $logFile -ErrorAction SilentlyContinue
        exit 1
    }
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  ✓ All migrations applied successfully!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""

# Verification
Write-Host "→ Verification:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Checking roadmaps table columns..."
& psql $supabaseDbUrl -c @"
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'roadmaps'
    AND column_name IN ('total_days', 'current_day');
"@ | Select-String "total_days|current_day" | ForEach-Object { Write-Host "    $_" }

Write-Host ""
Write-Host "  2. Checking handle_new_user trigger..."
& psql $supabaseDbUrl -c @"
    SELECT trigger_name, event_manipulation, action_statement
    FROM information_schema.triggers
    WHERE trigger_name = 'on_auth_user_created';
"@ | Select-String "on_auth_user_created|INSERT" | ForEach-Object { Write-Host "    $_" }

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Migration 5C Complete!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next step: 5D — Deploy to Railway"
Write-Host "  railway up" -ForegroundColor Cyan
Write-Host ""
