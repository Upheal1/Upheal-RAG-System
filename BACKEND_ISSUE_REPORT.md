# Backend Auth Issue — Full Report

## Current Error (June 1)
```
POST /api/assess → 401
{"detail":"Unable to resolve token signing key: Fail to fetch data from the url, err: \"HTTP Error 404: Not Found\""}
```

---

## What Was Fixed

The backend team merged two fixes into `main` (commits `667140b` + `d6ed786`):

### Fix 1: Auth Header Now Read
`get_current_user` was changed from:
```python
def get_current_user(authorization: Optional[str] = None)  # FastAPI never populates this
```
to:
```python
def get_current_user(request: Request) -> AuthenticatedUser:
    authorization = request.headers.get("Authorization")
```
This fixed the original `"Missing authorization header"` error.

### Fix 2: ES256 Token Support Added
The code now detects `alg: ES256` from the JWT header and tries to verify using JWKS via `PyJWKClient`.

---

## What's Still Broken

The token sent by Flutter Supabase SDK has `"alg":"ES256"`. The code detects this and fetches JWKS from:

```
{supabase_url}/.well-known/jwks.json
```

This URL returns **404**. The code has **no fallback** — it immediately raises `PyJWKClientError`, which surfaces as the 401 you see.

### Root Cause
This Supabase project does not expose a public JWKS endpoint. This is normal for Supabase projects on certain tiers. The JWT secret (`SUPABASE_JWT_SECRET`) is the correct way to verify tokens, but the current code doesn't try HS256 at all when the token header says ES256.

---

## What the 3-Tier Fix Would Do

| Tier | Method | What It Does |
|------|--------|-------------|
| 1 | HS256 with `SUPABASE_JWT_SECRET` | Tries first regardless of token algorithm header |
| 2 | ES256 via JWKS | Tries both `.well-known/jwks.json` URLs if HS256 fails |
| 3 | Unverified decode | Dev fallback with warning log |

---

## Files Referenced
- `services/gateway/auth_middleware.py` — all auth logic
- `tests/test_auth_middleware.py` — unit tests
- `docs/frontend_auth_report.md` — initial frontend report (outdated)
- `ANALYSIS_AND_SOLUTIONS.md` — backend analysis doc
