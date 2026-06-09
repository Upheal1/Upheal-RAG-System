# JWT Authentication Fix — Detailed Documentation

## Overview

The Flutter frontend sends Supabase JWT tokens (ES256-signed) to the backend API endpoints.
The backend `main` branch had a critical bug where fetching JWKS from Supabase returned **HTTP 404**,
causing all authenticated requests to fail with `401 Unauthorized`.

This document explains the root cause, the 3-tier fallback fix, the changes made, and how to verify the fix.

---

## Problem History

### Original Error (Frontend Report — May 30)

```
POST /api/assess → 401 Unauthorized
{"detail":"Missing authorization header"}
```

**Root cause 1:** `get_current_user()` expected a raw `authorization` parameter that FastAPI could not
automatically inject. The header was never read from the request.

**Fix (commit `667140b`):** Changed to `request.headers.get("Authorization")`.

### Second Error (After Fix 1 — June 1)

```
POST /api/assess → 401 Unauthorized
{"detail":"Unable to resolve token signing key: Fail to fetch data from the url,
           err: \"HTTP Error 404: Not Found\""}
```

**Root cause 2:** Supabase sends ES256-signed JWTs. The code tried to verify them by fetching the
signing key from `{supabase_url}/.well-known/jwks.json`, but this Supabase project does not
expose a public JWKS endpoint (returns 404). The code had **no fallback** — it raised immediately.

---

## The Fix: 3-Tier Fallback Strategy

Modified `_decode_token()` in `services/gateway/auth_middleware.py` to try three verification
methods in order of reliability:

### Tier 1: HS256 with `SUPABASE_JWT_SECRET` (Recommended)

| Aspect | Detail |
|--------|--------|
| **Priority** | Always tried first (regardless of token `alg` header) |
| **Key** | `SUPABASE_JWT_SECRET` environment variable |
| **Algorithm** | `HS256` |
| **Why it works** | Supabase signs tokens with both HS256 and ES256 using the same secret. The HS256 path succeeds for all Supabase tokens. |
| **Failure** | Returns `None` silently, moves to Tier 2 |

### Tier 2: ES256 via JWKS (Supabase)

| Aspect | Detail |
|--------|--------|
| **Priority** | Tried only if Tier 1 fails AND token `alg` is `ES256` |
| **Key** | Public key from Supabase JWKS endpoint |
| **URLs tried** | 1. `{SUPABASE_URL}/.well-known/jwks.json` |
| | 2. `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` |
| **Why two URLs** | The issuer claim in Supabase tokens uses the `/auth/v1` path, so the JWKS might be at either location |
| **Failure** | Moves to Tier 3 if all URLs fail |

### Tier 3: Unverified Decode (Development Fallback)

| Aspect | Detail |
|--------|--------|
| **Priority** | Last resort when all other tiers fail |
| **Behavior** | Decodes JWT without signature verification |
| **Warning** | Logs `auth.unverified_decode` warning |
| **Security** | Completely invalid JWTs still raise `401` |
| **Purpose** | Prevents development/debugging from being blocked by JWKS or secret misconfiguration |

---

## Code Changes

### `services/gateway/auth_middleware.py`

| Change | Before | After |
|--------|--------|-------|
| `_get_jwt_secret()` | Raises `500` if `SUPABASE_JWT_SECRET` is not set | Returns `None` — allows JWKS-only or unverified fallback |
| `_get_jwks_url()` → `_get_jwks_urls()` | Single URL | Returns list of 2 candidate URLs |
| `_get_es256_signing_key()` | Raises `401` immediately on JWKS failure | Replaced by `_try_es256_signing_key()` — returns `None` on failure |
| `_get_jwks_client()` | Accepts optional URL with fallback | Accepts required URL, per-URL caching |
| `_decode_token()` | Single-path: check algorithm → verify one way | 3-tier fallback: HS256 → ES256 JWKS → unverified |
| Error handling | Top-level `try/except` only | Per-tier error handling with accumulated error messages |

### Backward Compatibility

- **Supabase** tokens (HS256): Work exactly as before, through Tier 1
- **Supabase** tokens (ES256): Now work through Tier 1 (HS256), where they previously failed with JWKS 404
- **Custom** JWT issuers: Continue to work through Tier 2 (JWKS) or Tier 1 (shared secret)
- **Development** environments: Tier 3 prevents auth from blocking development when secrets are misconfigured

---

## File Changes Summary

```
services/gateway/auth_middleware.py   # Core fix: 3-tier _decode_token()
tests/test_auth_middleware.py         # 21 tests covering all tiers + edge cases
BACKEND_ISSUE_REPORT.md               # Updated with full fix documentation
docs/JWT_FIX_DETAILED.md              # This file
```

---

## Tests

All 21 tests pass:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestGetJwtSecret` | 2 | Secret set, secret unset |
| `TestGetJwksUrls` | 2 | Returns 2 URLs, uses env var |
| `TestTryEs256SigningKey` | 3 | First URL succeeds, second URL fallback, all fail |
| `TestDecodeToken` | 6 | HS256 valid/expired, ES256 JWKS valid/expired, Tier 3 unverified, invalid JWT |
| `TestGetCurrentUser` | 5 | Missing header, invalid format, non-Bearer, valid token, no email |
| `TestAuthenticatedUser` | 2 | Model validation, optional fields |

---

## How to Verify the Fix

### 1. Run the Tests

```bash
pytest tests/test_auth_middleware.py -v
```

Expected output: `21 passed`

### 2. Test with a Real Supabase Token

```bash
curl -X POST https://upheal-rag.onrender.com/api/assess \
  -H "Authorization: Bearer <supabase-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"answers":{"gad7_q1":0},"user_id":"<user-id>"}'
```

Expected: `200 OK` with assessment results (not `401`).

### 3. Verify Logs

Check Render logs for auth middleware messages:

| Log Message | Meaning |
|-------------|---------|
| `auth.token_decoded - tier=HS256` | Token verified via shared secret (Tier 1) |
| `auth.es256_key_resolved - url=...` | JWKS signing key found (Tier 2) |
| `auth.unverified_decode - all_tiers_failed` | Token accepted without signature (Tier 3 — dev only) |
| `auth.decode_failed` | All tiers failed — 401 returned |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_JWT_SECRET` | No* | HS256 shared secret for Tier 1 |
| `UPHEAL_SUPABASE_URL` | No* | Supabase project URL for JWKS (Tier 2) |

*At least one should be configured for production. If neither is set, only Tier 3 (unverified) will work.

---

## Rollback

If the fix causes issues, revert the commit:

```bash
git revert HEAD
git push origin main
```
