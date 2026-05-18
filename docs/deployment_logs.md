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

## Task 6B: Add Rate Limiting

**Date:** 2026-05-14  
**Owner:** Yehia (Y)  
**Status:** ✅ Completed

### Dependencies
- **Depends on:** 1D (Wire Auth on Core Endpoints) — completed

### Changes Made

#### 1. Modified `requirements.txt`
- Added `slowapi>=0.1.9` for rate limiting

#### 2. Modified `services/gateway/main.py`
- Imported `slowapi.Limiter` and `slowapi.util.get_remote_address`
- Created limiter with IP-based key function: `limiter = Limiter(key_func=get_remote_address)`
- Registered limiter on app state: `app.state.limiter = limiter`
- Added `@limiter.limit("10/minute")` decorator to `POST /api/assess` endpoint
- `/health` endpoint remains unlimited (as designed)

#### 3. Created `tests/test_rate_limiting.py`
- 8 passing unit tests covering rate limiting functionality

### Security Notes
- Rate limiting: 10 requests per minute per IP address
- Prevents abuse of `/api/assess` endpoint
- `/health` endpoint remains public and unlimited

### Files Changed
```
Modified:
  - requirements.txt
  - services/gateway/main.py

Added:
  - tests/test_rate_limiting.py
```

### Next Steps
- Proceed to task 6C (Scale Uvicorn Workers)
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

## Render Deployment — Health Check & OOM Fix

**Date:** 2026-05-17 – 2026-05-18
**Owner:** Ahmed (via opencode)
**Status:** ✅ Completed

### Problem

The UpHeal RAG System deployed to Render (free tier, 512MB RAM) had three cascading issues:

1. **502 Bad Gateway** — Render health checks use `HEAD` requests, but endpoints only supported `GET`
2. **OOM Crash** — `all-mpnet-base-v2` embedding model (420MB) was loaded at import time, exhausting RAM
3. **Knowledge Base Unhealthy** — `knowledge_base_healthy: false` on `/health` endpoint after OOM fix

### Changes Made

#### 1. HEAD Method Support (PR #48)

All 7 health endpoints now accept `HEAD` requests via `include_in_schema=False`:

| Endpoint | Change |
|----------|--------|
| `GET /health` | Added `@app.head("/health")` |
| `GET /knowledge_base/health` | Added `@router.head("/health")` |
| `GET /assessment/health` | Added `@router.head("/health")` |
| `GET /architect/health` | Added `@router.head("/health")` |
| `GET /ingestion/health` | Added `@router.head("/health")` |
| `GET /auditor/health` | Added `@router.head("/health")` |
| `GET /telemetry/health` | Added `@router.head("/health")` |

Files changed: `services/gateway/main.py`, `services/knowledge_base/router.py`, `services/assessment/router.py`, `services/architect/router.py`, `services/ingestion/router.py`, `services/auditor/router.py`, `services/telemetry/router.py`

#### 2. OOM Fix — Lazy Loading (PR #52)

- **`services/knowledge_base/chroma_adapter.py`**: `ChromaKnowledgeBase` now lazy-loads the embedding model via `_ensure_loaded()` instead of at `__init__` time
- **`services/knowledge_base/router.py`**: Changed from `_kb = ChromaKnowledgeBase()` (module-level) to `_kb = None` + `_get_kb()` lazy getter
- **`services/gateway/orchestrator.py`**: Same lazy pattern for `_kb`
- **`services/shared/state.py`**: Default model remains `all-mpnet-base-v2` (not switched to MiniLM)

#### 3. Lightweight Health Checks (PR #52)

Health checks no longer load the embedding model:

- **`/health`** — filesystem-based check: verifies `chroma.sqlite3` exists, counts UUID directories
- **`/knowledge_base/health`** — checks `chroma.sqlite3` exists, reads `config.json` for `last_ingestion`

#### 4. Collection Name Fix (PR #52)

- Changed default collection from `clinical_knowledge` to `clinical_rag_mini` to match actual data in `data/vector_db_mini/`

#### 5. Robust Path Resolution (PR #54)

**Root cause of `knowledge_base_healthy: false`:** Render runs the app from `/opt/render/project/src/`, but `UPHEAL_CHROMA_PATH` was set to `/app/data/vector_db_mini` (the Docker `WORKDIR`). The data directory existed at `/opt/render/project/src/data/vector_db_mini` but the path didn't match.

Added `resolve_chroma_path()` in `services/shared/pathing.py` — tries multiple paths in order:

1. `UPHEAL_CHROMA_PATH` env var (highest priority)
2. `./data/vector_db_mini` (relative to cwd)
3. `/opt/render/project/src/data/vector_db_mini` (Render)
4. `/app/data/vector_db_mini` (Docker default)
5. `repo_root()` fallback (local dev)

Returns the first path that exists as a directory.

Updated consumers:
- `services/gateway/main.py` — health check
- `services/knowledge_base/router.py` — `_kb_path()`
- `services/knowledge_base/chroma_adapter.py` — `ChromaKnowledgeBase.__init__`

#### 6. Debug Endpoint (PR #53)

Added temporary `/debug/paths` endpoint to diagnose path issues on Render. Revealed the CWD mismatch (`/opt/render/project/src` vs `/app`).

#### 7. `.dockerignore` (PR #54)

Created `.dockerignore` to reduce Docker build context from 430MB+ to ~136MB:

```
.git
venv/
__pycache__/
data/books/
data/vector_db_mini_enriched/
docs/
*.md
```

### Local Docker Testing

Built and tested minimal Docker containers locally to diagnose the data path issue:

| Test | Result |
|------|--------|
| `Dockerfile.test` — data files present in container? | ✅ `chroma.sqlite3` present, 3 UUID dirs |
| `Dockerfile.fasttest` — `COPY . .` from repo root | ✅ All data files copied |
| Fresh `git clone` from GitHub | ✅ `chroma.sqlite3` + 2 tracked UUID dirs |
| `debug/paths` on Render | ❌ CWD `/opt/render/project/src/`, not `/app` |

### Render Environment Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `UPHEAL_CHROMA_PATH` | `./data/vector_db_mini` | Changed from `/app/data/vector_db_mini` |
| `UPHEAL_CHROMA_COLLECTION` | `clinical_rag_mini` | Changed from `clinical_knowledge` |
| `SUPABASE_JWT_SECRET` | `dc5b9bc2-c652-4297-9bc3-4293082b9e76` | UUID-based key |
| `UPHEAL_SUPABASE_URL` | `https://gcxxmjptbyvlabqzcprv.supabase.co` | |
| `UPHEAL_SUPABASE_KEY` | `eyJ...` | Service role key |

### Files Changed

```
Modified:
  - services/gateway/main.py
  - services/knowledge_base/chroma_adapter.py
  - services/knowledge_base/router.py
  - services/gateway/orchestrator.py
  - services/shared/state.py
  - services/shared/pathing.py
  - services/assessment/router.py
  - services/architect/router.py
  - services/ingestion/router.py
  - services/auditor/router.py
  - services/telemetry/router.py
  - services/chat/router.py
  - services/journal/router.py
  - services/shared/env_validation.py
  - requirements.txt

Added:
  - .dockerignore
  - docs/EMBEDDING_MODEL_COMPARISON.md
  - deployments/Dockerfile.test
  - deployments/Dockerfile.fasttest
  - deployments/Dockerfile.dev
  - test_health_check.py

Tests:
  - tests/test_kb_router.py — updated for lightweight health checks
  - tests/test_rate_limiting.py — HEAD method support
  - tests/integration/test_chroma_adapter_real.py — explicit model_name
```

### PRs Merged

| PR | Title | Status |
|----|-------|--------|
| #48 | HEAD method support for health endpoints | ✅ Merged |
| #51 | Fix OOM crashes on Render free tier | ✅ Merged |
| #52 | Revert to all-mpnet-base-v2 + fix integration tests | ✅ Merged |
| #53 | Debug/paths endpoint | ✅ Merged |
| #54 | Robust ChromaDB path resolution for Render | ✅ Merged |

### Verified Results (after fix)

```json
// GET /health
{"status":"ok","knowledge_base_healthy":true,"knowledge_base_documents":2}

// GET /knowledge_base/health
{"indexed_tasks":2,"storage_status":"healthy","last_ingestion":null}
```

### Key Lessons

1. **Render CWD ≠ Docker WORKDIR**: Render runs from `/opt/render/project/src/`, not `/app/`. Always use relative paths or multi-path resolution.
2. **Docker build context is repo root**: When `dockerfile: deployments/Dockerfile` is in render.yaml, the build context is the repo root, not the Dockerfile's parent directory.
3. **Git-tracked files only**: Untracked files (`cd19becb-*`, `config.json`) are in local Docker builds but NOT on Render. Only git-tracked files make it into the container.
4. **Embedding models crash 512MB**: `all-mpnet-base-v2` (420MB) + ChromaDB + FastAPI = OOM. Lazy-loading defers the crash until actual query time and avoids loading on health checks.
5. **Render health checks use HEAD**: Must explicitly support `@router.head()` — FastAPI doesn't auto-support HEAD on GET routes.

---

## Session Summary: All Hozaifa Tasks Complete

**Date:** 2026-05-13
**Test Results:** 505 passed, 2 failed (pre-existing kb_router issues)

### Completed Tasks
- 1B, 1C, 1E, 2B, 2C, 2E, 3C, 5A, 5C, 6C, 6B (Yahya)

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
