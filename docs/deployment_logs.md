# UpHeal Deployment Logs

## Task 1A: RLS Policies — Migration 012

**Date:** 2026-05-12  
**Owner:** Yehia (Y) — taking over for Hozaifa  
**Status:** ✅ Completed

### Dependencies
- **Depends on:** Nothing

### Changes Made

#### 1. Created `supabase/migrations/012_enable_rls_policies.sql`
- Enable RLS on all user-facing tables
- Create policies for:
  - `users` — user can read/update/insert own row only
  - `user_profiles` — own profile only
  - `assessment_responses` — own responses only
  - `roadmaps` — own roadmaps only
  - `roadmap_tasks` — access via roadmap ownership
  - `interest_profiles` — own profile only
  - `chat_sessions` — own sessions only
  - `chat_messages` — access via session ownership
  - `interaction_logs` — own logs only
  - `xp_transactions` — own transactions only
  - `retrieval_logs` — own logs only
  - `roadmap_mutations` — own mutations only
  - `clinical_tasks` — read-only for authenticated
  - `retention_settings` — service role only (no access)

#### 2. Updated `supabase/combined_migrations.sql`
- Appended migration 012

#### 3. Updated `supabase/README.md`
- Added migration 012 to the migration order table

### Security Notes
- Without RLS, anyone with the anon key can read/write every table
- This is the single biggest security gap
- All policies use `auth.uid() = user_id` for ownership validation

### Files Changed
```
Added:
  - supabase/migrations/012_enable_rls_policies.sql

Modified:
  - supabase/combined_migrations.sql
  - supabase/README.md
```

### Next Steps
- Run migration on Supabase: `supabase db push` or `psql`
- Proceed to task 1B (Startup Environment Validation)

---

## Task 1D: Wire Auth on Core Endpoints

**Date:** 2026-05-12  
**Owner:** Yehia (Y)  
**Status:** ✅ Completed

### Dependencies
- **Blocked by:** 1B (Startup Environment Validation) — completed by Hozaifa

### Changes Made

#### 1. Created `services/gateway/auth_middleware.py`
- JWT validation using Supabase JWT secret
- `get_current_user()` FastAPI dependency
- `AuthenticatedUser` model with `user_id`, `email`, `exp`
- Proper 401 responses for missing/invalid tokens

#### 2. Modified `services/gateway/main.py`
- Added auth dependency on `POST /api/assess`
- Added auth dependency on `POST /api/roadmap`
- **Security fix:** `user_id` now comes from JWT token (`user.user_id`) instead of request payload
- Prevents user impersonation attacks

#### 3. Updated `requirements.txt`
- Added `PyJWT>=2.8.0` for JWT decoding

#### 4. Created `tests/test_auth_middleware.py`
- 13 passing unit tests covering:
  - JWT secret validation
  - Token decoding (valid, expired, invalid)
  - Authorization header parsing
  - AuthenticatedUser model

### Security Notes
- `/health` endpoint remains public (as designed)
- `/knowledge_base/*`, `/ingestion/*`, `/assessment/*` health endpoints remain public
- user_id from payload is ignored; JWT 'sub' claim is the source of truth

### Files Changed
```
Modified:
  - requirements.txt
  - services/gateway/main.py

Added:
  - services/gateway/auth_middleware.py
  - tests/test_auth_middleware.py
```

### Next Steps
- Merge to staging branch
- Coordinate with frontend team (Abdalrahman) for JWT token integration
- Proceed to task 2A (Roadmap Schemas)

---

## Task 2A: Roadmap Schemas

**Date:** 2026-05-12  
**Owner:** Yehia (Y)  
**Status:** ✅ Completed

### Dependencies
- **Depends on:** Nothing (can start in parallel)

### Changes Made

#### 1. Modified `services/shared/schemas.py`
- Added `RoadmapDay` class with fields: `day_number`, `task`, `phase`, `day_context`
- Added `ReassessmentStatus` class with fields: `user_id`, `roadmap_id`, `roadmap_status`, `current_day`, `total_days`, `assessment_required`, `days_since_last_assessment`

#### 2. Modified `services/gateway/schemas.py`
- Updated `RoadmapResponse` to include:
  - `days: List[RoadmapDay]` - list of 90 days
  - `total_days: int = 90` - default 90
  - `assessment_required: bool = False` - whether user needs reassessment

#### 3. Created `tests/test_roadmap_schemas.py`
- 13 passing unit tests covering:
  - RoadmapDay validation (day_number bounds, phase values)
  - ReassessmentStatus defaults and fields
  - RoadmapResponse with 90-day roadmap
  - RoadmapRequest validation

### Files Changed
```
Modified:
  - services/shared/schemas.py
  - services/gateway/schemas.py

Added:
  - tests/test_roadmap_schemas.py
```

### Next Steps
- Proceed to task 2D (Roadmap Status + Re-Assessment Endpoint) — depends on 2A

---

## Task 2D: Roadmap Status + Re-Assessment Endpoint

**Date:** 2026-05-12  
**Owner:** Yehia (Y)  
**Status:** ✅ Completed

### Dependencies
- **Depends on:** 1D (auth wired), 2A (schemas)

### Changes Made

#### 1. Created `services/roadmap/router.py`
- New router with `GET /{user_id}/status` endpoint
- Returns `ReassessmentStatus` with roadmap info
- Auth required (user can only access own status)
- Handles edge cases: no roadmap, completed, expired

#### 2. Modified `services/gateway/main.py`
- Added import for `services.roadmap.router`
- Registered roadmap router at `/api/roadmap` prefix

#### 3. Created `tests/test_roadmap_status.py`
- 6 passing tests covering:
  - No roadmap returns assessment_required=True
  - Active roadmap under 90 days
  - Roadmap over 90 days
  - Completed roadmap
  - Auth required
  - Health endpoint

### Files Changed
```
Modified:
  - services/gateway/main.py

Added:
  - services/roadmap/router.py
  - tests/test_roadmap_status.py
```

### Next Steps
- Proceed to task 2E (Supabase Migration for 90-Day Roadmap)
---

## Task 1B: Startup Environment Validation

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Created services/shared/env_validation.py - validates SUPABASE_JWT_SECRET on startup
2. Modified services/gateway/main.py - added startup event to call validate_env()

---

## Task 1C: Add SUPABASE_JWT_SECRET to Env Configs

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified .env.example - added SUPABASE_JWT_SECRET
2. Modified deployments/.env.example - added SUPABASE_JWT_SECRET
3. Modified deployments/docker-compose.yml - added SUPABASE_JWT_SECRET env var
4. Modified deployments/render.yaml - added SUPABASE_JWT_SECRET, UPHEAL_SUPABASE_URL, UPHEAL_SUPABASE_KEY

---

## Task 1E: Parameterize CORS

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified services/gateway/main.py - CORS now uses ALLOWED_ORIGINS env var (defaults to "*" in dev)

---

## Task 2B: 90-Day Task Generation Algorithm

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified services/architect/pipeline.py - added generate_ninety_day_plan() function with Quick Win/Ladder/Boss phases
2. Modified services/shared/schemas.py - added days, total_days, assessment_required to FinalRoadmap

---

## Task 2C: 90-Day Roadmap in Orchestrator

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified services/architect/pipeline.py - integrated 90-day plan generation into run_architect_pipeline()
2. Modified services/gateway/main.py - added days, total_days, assessment_required to RoadmapResponse

---

## Task 2E: Supabase Migration for 90-Day Roadmap

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Created supabase/migrations/013_roadmap_ninety_day.sql - added total_days, current_day columns and auth trigger
2. Modified supabase/combined_migrations.sql - appended migration 013
3. Modified supabase/README.md - added migration 013 to index
4. Created scripts/run_migrations.sh and scripts/run_migrations.ps1 - migration runner scripts

---

## Task 3C: Per-App Social/Detox Penalty in Architect Scoring

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified services/shared/schemas.py - added AppPercentage model and appBreakdown to ScreenTimeInsights
2. Modified services/assessment/core.py - updated parse_screen_time_data() to compute app_breakdown
3. Modified services/architect/pipeline.py - added _calculate_social_heavy_penalty() and updated rerank_tasks()

---

## Task 5A: Update railway.json with All Env Vars

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified deployments/railway.json - complete rewrite with all required env vars (SUPABASE_JWT_SECRET, UPHEAL_SUPABASE_URL, etc.)

---

## Task 5C: Run Supabase Migrations

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed (Ready to Run)

### Changes Made
1. Created scripts/run_migrations.sh - bash migration runner
2. Created scripts/run_migrations.ps1 - PowerShell migration runner

---

## Task 6C: Scale Uvicorn Workers

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? Completed

### Changes Made
1. Modified deployments/Dockerfile - added --workers 2 to uvicorn CMD

---

## Session Summary: All Hozaifa Tasks Complete

**Date:** 2026-05-13
**Test Results:** 505 passed, 2 failed (pre-existing kb_router issues)

### Completed Tasks
- 1B, 1C, 1E, 2B, 2C, 2E, 3C, 5A, 5C, 6C

### Next Steps
- 5B: Set Railway Secrets (SUPABASE_JWT_SECRET, UPHEAL_SUPABASE_KEY)
- 5D: Deploy to Railway
- 6A: Lock CORS (after deployment URL known)
- 6B: Rate Limiting (Yahya)

---

## Task 5C: Run Supabase Migrations - PRODUCTION COMPLETE

**Date:** 2026-05-13
**Owner:** Hozaifa (H)
**Status:** ? COMPLETED ON PRODUCTION

### Execution Method
Applied via Supabase Dashboard SQL Editor (Option 1)

### Migrations Applied
- **012_enable_rls_policies.sql** - RLS policies on all tables
- **013_roadmap_ninety_day.sql** - 90-day roadmap columns + auth trigger

### Verification SQL (Run in Supabase SQL Editor)
`sql
-- Verify roadmaps table has new columns
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'roadmaps'
AND column_name IN ('total_days', 'current_day');

-- Expected output:
-- total_days | integer | 90
-- current_day | integer | 1

-- Verify trigger exists
SELECT trigger_name, event_manipulation
FROM information_schema.triggers
WHERE trigger_name = 'on_auth_user_created';

-- Expected output:
-- on_auth_user_created | INSERT
`

### Next Steps
- ? 5C Complete
- ? 5D: Deploy to Railway
- ? 5B: Set Railway Secrets (SUPABASE_JWT_SECRET, UPHEAL_SUPABASE_KEY)

---
