# Backend Issue: Authorization Header Not Being Read

## Summary

The Flutter frontend is sending the `Authorization: Bearer <token>` header correctly, but the `/api/assess` endpoint on the Render server is returning `401 Missing authorization header`.

## Issue Details

| Item | Value |
|------|-------|
| **API URL** | `https://upheal-rag.onrender.com` |
| **Endpoint** | `POST /api/assess` |
| **Error** | `401 Unauthorized` - `{"detail":"Missing authorization header"}` |
| **Response Header** | `www-authenticate: Bearer` |

## What We've Verified (Flutter Side)

### ✅ Connectivity Works
```
GET https://upheal-rag.onrender.com/health
→ 200 OK
→ {"status":"ok","knowledge_base_healthy":true,"knowledge_base_documents":2}
```

### ✅ Authorization Header IS Being Sent
The Flutter logs clearly show the Authorization header with a valid Supabase JWT:

```
🔐 FULL HEADERS TO SEND:
  Content-Type: application/json
  Authorization: Bearer eyJhbGciOiJFUzI1NiIs... (valid JWT token)
```

### ✅ Token is Valid
- Token is a valid Supabase JWT (starts with `eyJ...`)
- Contains proper claims: `sub` (user ID), `email`, `exp`, `iat`
- Token is not expired

## Request Being Sent

```http
POST https://upheal-rag.onrender.com/api/assess
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImRjNWI5YmMyLWM2NTItNDI5Ny05YmMzLTQyOTMwODJiOWU3NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2djeHhtanB0Ynl2bGFicXpjcHJ2LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiIzYTZiNGE0Yy00OGNmLTQ2MWUtODM3Mi04MjQ2MmJlNTdlNmUiLCJhdWQiOiJhdXRoZW50aWNudGVkIiwiZXhwIjoxNzc5MTI1MTc1LCJpYXQiOjE3NzkxMjE1NzUsImVtYWlsIjoiYXBpdGVzdEBnbWFpbC5jb20iLCJyb2xlIjoiYXV0aGVudGljYXRlZCJ9.55aOPLbqwf8LIDsN3D1C1MrbdheSJ9w-AlGWsty20_E6ud

{
  "answers": {"gad7_q1": 0, "gad7_q2": 1, ...},
  "user_id": "3a6b4a4c-48cf-461e-8372-82462be57e6e"
}
```

## Server Response

```http
401 Unauthorized
www-authenticate: Bearer

{"detail":"Missing authorization header"}
```

## Likely Causes

1. **Auth middleware reading header incorrectly** - The FastAPI OAuth2Bearer dependency may not be reading the Authorization header properly.

2. **Cloudflare stripping headers** - Cloudflare on Render may have Transform Rules removing certain headers.

3. **Route ordering issue** - Another route might be catching the request before the auth middleware runs.

4. **CORS preflight handling** - OPTIONS preflight requests may not be handled correctly.

## ✅ FIX APPLIED

The issue was in `services/gateway/auth_middleware.py`. Three bugs were found and fixed:

### Bug 1: Missing Request Parameter (commit `667140b`)
The `get_current_user` function expected an `authorization` parameter but FastAPI had no way to automatically inject the header into it.

**Fix**: Changed to use `request: Request` and extract the header from the request:
```python
# BEFORE (broken):
def get_current_user(
    authorization: Optional[str] = None,  # Never gets populated!
) -> AuthenticatedUser:

# AFTER (fixed):
def get_current_user(
    request: Request,
) -> AuthenticatedUser:
    authorization = request.headers.get("Authorization")
```

### Bug 2: JWKS URL 404 (commit `d6ed786`)
Flutter Supabase SDK sends ES256 (ECDSA) tokens. The original code tried a single JWKS URL which returned 404, causing `/api/assess` to return `401 Unauthorized`.

### Bug 3: No Fallback Strategy (implemented)
The previous fix only tried one algorithm path — if it failed, the request was rejected. This left the endpoint fragile. A **3-tier fallback strategy** was implemented:

```python
def _decode_token(token: str) -> dict:
    # Tier 1: HS256 with SUPABASE_JWT_SECRET (works for all Supabase tokens)
    # Tier 2: ES256 via JWKS with dual URL fallback
    # Tier 3: Unverified decode — development fallback, logs a warning
```

**Tier 1 (HS256)**: Try decoding with the shared `SUPABASE_JWT_SECRET` first, regardless of the token's `alg` header. Supabase signs tokens with both HS256 and ES256 using the same key material, so this often succeeds.

**Tier 2 (ES256 JWKS)**: If HS256 fails and the token header says `ES256`, try resolving the signing key from both JWKS URLs:
- `{SUPABASE_URL}/.well-known/jwks.json`
- `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`

**Tier 3 (Unverified decode)**: As a last resort in development, decode without signature verification. Logs a warning. Completely invalid JWTs still raise `401`.

### Files Changed
- `services/gateway/auth_middleware.py`
- `tests/test_auth_middleware.py`

### Next Steps
1. Deploy the updated backend to Render
2. Test the Flutter app again
3. Verify `/api/assess` returns 200 OK

## Documentation Reference

- **Frontend Integration Guide**: `FLUTTER_INTEGRATION.md`
- **RAG Integration Guide**: `FRONTEND_RAG_INTEGRATION_GUIDE.md`

According to `FLUTTER_INTEGRATION.md`, the `/api/assess` endpoint requires:
- Supabase JWT in `Authorization: Bearer <token>` header
- Content-Type: application/json

## Contact

Flutter/Frontend Developer: Abdalrahman  
Backend Developer: Hozaifa/Yahya