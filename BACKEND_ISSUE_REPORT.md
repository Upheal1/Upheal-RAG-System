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

The issue was in `services/gateway/auth_middleware.py`. Two bugs were found and fixed:

### Bug 1: Missing Request Parameter
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

### Bug 2: ES256 Token Support
The Flutter Supabase SDK sends ES256 (ECDSA) tokens, but the backend only supported HS256.

**Fix**: Added JWKS fetching from Supabase to support ES256:
```python
def _decode_token(token: str) -> dict:
    # Detect algorithm from token header
    header = jwt.get_unverified_header(token)
    
    if algorithm == "ES256":
        # Fetch JWKS from Supabase for verification
        jwks = _get_jwks()
        payload = jwt.decode(token, jwks, algorithms=["ES256"])
    else:
        # HS256 with JWT secret
        payload = jwt.decode(token, secret, algorithms=["HS256"])
```

### Files Changed
- `services/gateway/auth_middleware.py`

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