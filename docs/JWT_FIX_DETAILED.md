# JWT Authentication Fix - Detailed Documentation

## Overview

The Flutter frontend sends Supabase JWT tokens to the backend API endpoints.
The backend previously failed authenticated requests when it could not resolve the JWT signing key
from Supabase JWKS, often returning `401 Unauthorized`.

This document explains the root cause, the verified JWT fallback fix, the changes made, and how to
verify the fix.

---

## Problem History

### Original Error (Frontend Report - May 30)

```text
POST /api/assess -> 401 Unauthorized
{"detail":"Missing authorization header"}
```

**Root cause 1:** `get_current_user()` expected a raw `authorization` parameter that FastAPI could not
automatically inject. The header was never read from the request.

**Fix:** Changed auth extraction to `request.headers.get("Authorization")`.

### Second Error (After Fix 1 - June 1)

```text
POST /api/assess -> 401 Unauthorized
{"detail":"Unable to resolve token signing key: Fail to fetch data from the url,
           err: \"HTTP Error 404: Not Found\""}
```

**Root cause 2:** Supabase may send ES256-signed JWTs. The code tried to verify them by fetching the
signing key from a single JWKS URL. If that URL returned 404, the request failed immediately.

---

## The Fix: Verified JWT Strategy

Modified `_decode_token()` in `services/gateway/auth_middleware.py` to try verified decoding methods
in order. Unverified decoding is blocked by default and can only be enabled explicitly for local
development.

### Tier 1: HS256 with `SUPABASE_JWT_SECRET`

| Aspect | Detail |
|--------|--------|
| **Priority** | Tried first when `SUPABASE_JWT_SECRET` is configured |
| **Key** | `SUPABASE_JWT_SECRET` environment variable |
| **Algorithm** | `HS256` |
| **Why it works** | Supports legacy/shared-secret JWTs signed with HS256 |
| **Failure** | Moves to Tier 2 when the token is not valid for HS256 |

### Tier 2: ES256 via JWKS

| Aspect | Detail |
|--------|--------|
| **Priority** | Tried only if Tier 1 fails and the token `alg` is `ES256` |
| **Key** | Public key from Supabase JWKS endpoint |
| **URLs tried** | 1. `{SUPABASE_URL}/.well-known/jwks.json` |
| | 2. `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` |
| **Why two URLs** | The issuer claim in Supabase tokens uses the `/auth/v1` path, so the JWKS may be at either location |
| **Failure** | Returns `401 Unauthorized` unless local development has explicitly enabled unverified decoding |

### Tier 3: Optional Unverified Decode (Local Development Only)

| Aspect | Detail |
|--------|--------|
| **Priority** | Last resort when all verified methods fail |
| **Behavior** | Decodes JWT without signature verification only when `ALLOW_UNVERIFIED_JWT=true` |
| **Warning** | Logs `auth.unverified_decode` warning |
| **Security** | Disabled by default. Do not enable in production because forged JWTs could authenticate as arbitrary users. |
| **Purpose** | Prevents local development/debugging from being blocked by JWKS or secret misconfiguration |

---

## Code Changes

### `services/gateway/auth_middleware.py`

| Change | Before | After |
|--------|--------|-------|
| Header extraction | FastAPI dependency did not reliably receive the raw auth header | Reads `request.headers.get("Authorization")` |
| `_get_jwks_url()` -> `_get_jwks_urls()` | Single URL | Returns 2 candidate JWKS URLs |
| `_get_es256_signing_key()` | Raised immediately on JWKS failure | Replaced by `_try_es256_signing_key()`, which tries each JWKS URL |
| `_decode_token()` | Single-path token validation | Verified fallback: HS256 -> ES256 JWKS; optional dev-only unverified decode |
| Unverified decode | Could run automatically after verified methods failed | Disabled by default; requires `ALLOW_UNVERIFIED_JWT=true` |
| Missing-header logging | Logged all request headers | Logs only `auth.missing_header` to avoid leaking sensitive headers |

### Backward Compatibility

- **Supabase tokens (HS256):** Work through Tier 1.
- **Supabase tokens (ES256):** Work through Tier 2 when the token's `kid` can be resolved from Supabase JWKS.
- **Custom JWT issuers:** Continue to work through Tier 2 (JWKS) or Tier 1 (shared secret).
- **Development environments:** Tier 3 is available only when `ALLOW_UNVERIFIED_JWT=true`.

---

## File Changes Summary

```text
services/gateway/auth_middleware.py   # Core fix: verified _decode_token() with dev-only fallback
tests/test_auth_middleware.py         # Tests covering verified auth + dev-only fallback edge cases
docs/JWT_FIX_DETAILED.md              # This file
```

---

## Tests

All focused auth tests pass:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestGetJwtSecret` | 2 | Secret set, secret unset |
| `TestGetJwksUrls` | 2 | Returns 2 URLs, uses env var |
| `TestTryEs256SigningKey` | 3 | First URL succeeds, second URL fallback, all fail |
| `TestDecodeToken` | 7 | HS256 valid/expired, ES256 JWKS valid/expired, unverified disabled by default, dev-only unverified, invalid JWT |
| `TestGetCurrentUser` | 5 | Missing header, invalid format, non-Bearer, valid token, no email |
| `TestAuthenticatedUser` | 2 | Model validation, optional fields |

---

## How to Verify the Fix

### 1. Run the Tests

```bash
pytest tests/test_auth_middleware.py -v
```

Expected output: all tests pass.

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
| `auth.unverified_decode - all_tiers_failed` | Token accepted without signature only because `ALLOW_UNVERIFIED_JWT=true` is set |
| `auth.decode_failed` | All verified tiers failed and the request returned `401` |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_JWT_SECRET` | Yes for current startup validation | HS256 shared secret for Tier 1 |
| `UPHEAL_SUPABASE_URL` | Recommended | Supabase project URL for JWKS (Tier 2) |
| `ALLOW_UNVERIFIED_JWT` | No | Local-development-only fallback. Never enable in production. |

Production must use verified JWT validation. The current startup validation still requires
`SUPABASE_JWT_SECRET`; ES256 support additionally depends on `UPHEAL_SUPABASE_URL` pointing to the
Supabase project that exposes `/auth/v1/.well-known/jwks.json`.

---

## Rollback

If the fix causes issues, revert the commit:

```bash
git revert HEAD
git push origin main
```
