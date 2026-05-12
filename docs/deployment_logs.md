# UpHeal Deployment Logs

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