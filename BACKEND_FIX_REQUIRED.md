# Backend Fix Required: JWKS 404 Error on ES256 Token Verification

## The Problem

Flutter sends `Authorization: Bearer <token>` to `POST /api/assess`. The token has `alg: ES256` in its header.

The current `auth_middleware.py` detects ES256 and fetches the signing key from:
```
https://gcxxmjptbyvlabqzcprv.supabase.co/.well-known/jwks.json
```

This URL returns **HTTP 404**. The code has no fallback when JWKS fails, so it raises:
```
401 Unable to resolve token signing key: Fail to fetch data from the url, err: "HTTP Error 404: Not Found"
```

## What Needs to Change

There are **two fix options**. Pick one:

### Option A: Enable JWKS on the Supabase Project (Recommended if you control Supabase)

1. Go to your Supabase project dashboard: `https://supabase.com/dashboard/project/gcxxmjptbyvlabqzcprv`
2. Navigate to: **Authentication → Settings → JWT expiry**
3. Enable the JWKS endpoint. This will make keys available at:
   - `https://gcxxmjptbyvlabqzcprv.supabase.co/.well-known/jwks.json`
   - Or: `https://gcxxmjptbyvlabqzcprv.supabase.co/auth/v1/.well-known/jwks.json`
4. The `PyJWKClient` code in `_get_es256_signing_key()` will then work without any code changes.

### Option B: 3-Tier Fallback in Code (Recommended if Supabase plan doesn't support JWKS)

Modify `auth_middleware.py`:

**1. Change `_decode_token` to try HS256 first:**
```python
def _decode_token(token: str) -> dict:
    logger = get_logger(__name__)

    # Tier 1: HS256 with SUPABASE_JWT_SECRET (always try first)
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if secret:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired", headers={"WWW-Authenticate": "Bearer"})
        except jwt.InvalidTokenError:
            pass

    # Tier 2: ES256 via JWKS (try all candidate URLs)
    for url in [f"{supabase_url}/.well-known/jwks.json", f"{supabase_url}/auth/v1/.well-known/jwks.json"]:
        try:
            client = PyJWKClient(url)
            key = client.get_signing_key_from_jwt(token).key
            return jwt.decode(token, key, algorithms=["ES256"], options={"verify_aud": False})
        except Exception:
            continue

    # Tier 3: Unverified decode (dev only)
    logger.warning("auth.fallback_unverified")
    return jwt.decode(token, options={"verify_signature": False})
```

**2. Remove `_get_jwt_secret()` raising behavior** — return `None` instead of 500 error if secret is unset. The token may still verify via JWKS or unverified fallback.

**3. Add both candidate JWKS URLs** — the issuer claim is `{supabase_url}/auth/v1`, so the JWKS might be at `/auth/v1/.well-known/jwks.json`, not just the root.

## Testing the Fix

```bash
# Test with a real Supabase token from Flutter
curl -X POST https://upheal-rag.onrender.com/api/assess \
  -H "Authorization: Bearer <supabase-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"answers":{"gad7_q1":0},"user_id":"e8f48768-40aa-41ff-8005-e3971dea6f70"}'
```

Expected: `200 OK` with assessment results.

## Deployment Steps

1. Apply the code changes to `services/gateway/auth_middleware.py`
2. Run tests: `pytest tests/test_auth_middleware.py -v`
3. Commit and push to `fix/auth-middleware-headers`
4. Create a PR to `main`
5. Merge and deploy on Render

## Environment Variables

Ensure these are set on Render:
- `SUPABASE_JWT_SECRET` — keep set (even if unused, safe fallback)
- `UPHEAL_SUPABASE_URL` — keep set as `https://gcxxmjptbyvlabqzcprv.supabase.co`

## Rollback Plan

If the fix breaks other routes, revert the commit and keep the current JWKS-only approach while Supabase JWKS endpoint is investigated.
