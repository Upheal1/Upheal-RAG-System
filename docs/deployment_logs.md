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