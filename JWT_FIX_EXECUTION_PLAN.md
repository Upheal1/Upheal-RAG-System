# JWT Fix Execution Plan

## Context

The Flutter frontend sends `Authorization: Bearer <token>` to `POST /api/assess`, but production returned:

```http
401 Unauthorized
{"detail":"Missing authorization header"}
```

`BACKEND_ISSUE_REPORT.md` showed two suspected backend issues:

1. The auth dependency previously did not receive the request headers correctly.
2. Supabase now sends ES256 JWTs, while the backend originally only handled HS256.

## Execution Plan

1. Read `BACKEND_ISSUE_REPORT.md` and confirm the reported endpoint and failure mode.
2. Inspect `services/gateway/main.py` to verify which auth dependency protects `POST /api/assess`.
3. Inspect `services/gateway/auth_middleware.py` to confirm whether the header extraction fix is already present.
4. Audit the ES256 JWT path for correct Supabase JWKS key lookup.
5. Update backend auth code so ES256 tokens are verified with the signing key selected from Supabase JWKS.
6. Remove unsafe ES256 fallback behavior that decoded tokens without signature verification.
7. Update tests to match the current `get_current_user(request: Request)` dependency shape.
8. Add a focused ES256 token test that verifies the backend decodes a Supabase-style JWT through the signing-key path.
9. Run targeted auth tests.
10. If tests pass, deploy the backend and verify with a real Flutter/Supabase token against Render.

## Findings

`services/gateway/main.py` correctly protects `POST /api/assess` with:

```python
user: AuthenticatedUser = Depends(get_current_user)
```

`services/gateway/auth_middleware.py` already had the request-header extraction fix:

```python
authorization = request.headers.get("Authorization")
```

The remaining risk was ES256 verification. The previous code fetched JWKS but passed the whole JWKS dictionary into `jwt.decode(...)`. PyJWT expects the actual signing key that matches the token header `kid`. The previous code also fell back to decoding ES256 tokens without signature verification when JWKS lookup failed.

## Changes Made

### `services/gateway/auth_middleware.py`

- Added `PyJWKClient` based JWKS support.
- Added `_get_jwks_url()` to build the Supabase JWKS endpoint from `UPHEAL_SUPABASE_URL`.
- Added `_get_jwks_client()` with per-URL caching.
- Added `_get_es256_signing_key()` to select the correct signing key from the token `kid`.
- Changed ES256 validation to call `jwt.decode(...)` with the resolved public signing key.
- Removed the unsafe unverified ES256 decode fallback.
- Changed HS256 validation so `SUPABASE_JWT_SECRET` is required only for HS256 tokens, not for ES256 tokens.

### `tests/test_auth_middleware.py`

- Updated tests to call `get_current_user(...)` with a request-like object instead of a raw authorization string.
- Added an ES256 branch test with a Supabase-style JWT header.
- Mocked the signing-key resolver and `jwt.decode(...)` in the ES256 test so the test does not depend on network access or local cryptography packages.

### Frontend Folder

The Flutter client in `C:\Users\Lenovo\Documents\GitHub\frontend` also had a request-side issue:

- `lib/services/upheal_api.dart` sent `Content-Type` but no `Authorization` header.
- `lib/screens/gad_phq_form_screen.dart` originally submitted assessments without an auth token. It now uses the Supabase user id and Supabase access token.

Changes were documented in:

```text
C:\Users\Lenovo\Documents\GitHub\frontend\RAG_JWT_FIX_NOTES.md
```

The frontend has since been migrated to Supabase Auth, so its RAG calls now send a Supabase access token that matches this backend validator.

## Deployment Checklist

1. Confirm production uses Supabase Auth.
2. Confirm Render is deploying the current repo commit that contains the auth middleware changes.
3. If using Supabase, confirm `UPHEAL_SUPABASE_URL` is set to the Supabase project URL, for example:

   ```env
   UPHEAL_SUPABASE_URL=https://gcxxmjptbyvlabqzcprv.supabase.co
   ```

4. Keep `SUPABASE_JWT_SECRET` set if HS256 compatibility is still needed.
5. Redeploy the backend on Render.
6. Test `POST /api/assess` with a real Supabase access token:

   ```bash
   curl -X POST https://upheal-rag.onrender.com/api/assess \
     -H "Authorization: Bearer <valid-supabase-access-token>" \
     -H "Content-Type: application/json" \
     -d '{"answers":{"gad7_q1":0},"user_id":"<supabase-user-id>"}'
   ```

7. If production still returns `Missing authorization header`, check Render logs for `auth.missing_header`; that would mean the request is reaching FastAPI without the header.

## Expected Result

Valid Supabase ES256 access tokens should be accepted by `/api/assess`, `/api/roadmap`, chat, roadmap status, and any other route using `Depends(get_current_user)`.
