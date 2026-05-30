# Backend Issue: Authorization Header Not Being Read

> **Source:** Frontend Team Report (Abdalrahman)  
> **Date:** 2026-05-30  
> **Status:** Open — Backend investigation required  
> **Backend Owners:** Hozaifa / Yahya

---

## Summary

The Flutter frontend is sending the `Authorization: Bearer <token>` header correctly, but the `/api/assess` endpoint on the Render server is returning `401 Missing authorization header`.

---

## Issue Details

| Item | Value |
|------|-------|
| **API URL** | `https://upheal-rag.onrender.com` |
| **Endpoint** | `POST /api/assess` |
| **Error** | `401 Unauthorized` - `{"detail":"Missing authorization header"}` |
| **Response Header** | `www-authenticate: Bearer` |

---

## Frontend Verification

### Connectivity Works
```
GET https://upheal-rag.onrender.com/health
→ 200 OK
→ {"status":"ok","knowledge_base_healthy":true,"knowledge_base_documents":2}
```

### Authorization Header IS Being Sent
Flutter logs show the header with a valid Supabase JWT:
```
FULL HEADERS TO SEND:
  Content-Type: application/json
  Authorization: Bearer eyJhbGciOiJFUzI1NiIs... (valid JWT token)
```

### Token is Valid
- Token is a valid Supabase JWT (starts with `eyJ...`)
- Contains proper claims: `sub` (user ID), `email`, `exp`, `iat`
- Token is not expired

---

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

---

## Server Response

```http
401 Unauthorized
www-authenticate: Bearer

{"detail":"Missing authorization header"}
```

---

## Likely Causes

1. **Auth middleware reading header incorrectly** — The FastAPI OAuth2Bearer dependency may not be reading the Authorization header properly.
2. **Cloudflare stripping headers** — Cloudflare on Render may have Transform Rules removing certain headers.
3. **Route ordering issue** — Another route might be catching the request before the auth middleware runs.
4. **CORS preflight handling** — OPTIONS preflight requests may not be handled correctly.

---

## Required Fix (Backend Side)

### Step 1: Add Debug Logging

Add debug logging to `/api/assess` to see what's actually being received:

```python
from fastapi import Request

@app.post("/api/assess")
async def assess(request: Request):
    # DEBUG: Print all headers
    print("=" * 50)
    print("ALL HEADERS RECEIVED:")
    for key, value in request.headers.items():
        print(f"  {key}: {value}")
    print("=" * 50)

    auth_header = request.headers.get("Authorization")
    print(f"Authorization header value: {auth_header}")
    print(f"Authorization header type: {type(auth_header)}")

    # Continue with existing logic...
```

### Step 2: Verify Auth Dependency

Check that the auth dependency is correctly configured:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    print(f"Token received: {token[:50]}...")  # Debug print
    # Your JWT validation logic...
```

### Step 3: Check Cloudflare Settings

Verify there are no Cloudflare Transform Rules that might be stripping the Authorization header.

### Step 4: Test with curl

Test the endpoint manually with curl to isolate the issue:

```bash
# Get a valid token from Supabase, then test:
curl -X POST https://upheal-rag.onrender.com/api/assess \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPABASE_TOKEN" \
  -d '{"answers":{"gad7_q1":0},"user_id":"test"}'
```

---

## Related Documentation

- **Frontend Integration Guide**: `FLUTTER_INTEGRATION.md`
- **RAG Integration Guide**: `FRONTEND_RAG_INTEGRATION_GUIDE.md`
- According to `FLUTTER_INTEGRATION.md`, the `/api/assess` endpoint requires:
  - Supabase JWT in `Authorization: Bearer <token>` header
  - Content-Type: application/json

---

## Contact

- **Flutter/Frontend Developer:** Abdalrahman
- **Backend Developer:** Hozaifa / Yahya

---

## Todo Checklist for Backend Team

- [ ] Add debug logging to `/api/assess` to inspect received headers
- [ ] Verify Auth dependency (`HTTPBearer` / `OAuth2`) configuration for `/api/assess`
- [ ] Check route ordering to ensure auth middleware runs before `/api/assess`
- [ ] Test endpoint locally with curl using a valid Supabase JWT
- [ ] Verify CORS preflight (`OPTIONS`) handling does not strip `Authorization`
- [ ] Check if Cloudflare/Render is stripping the `Authorization` header
- [ ] Update relevant docs (`AGENTS.md`) if auth middleware behavior changes
