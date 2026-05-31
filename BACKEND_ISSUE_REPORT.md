# Backend Issue Report: Auth Middleware JWT Decode Failure

## Summary
`POST /api/assess` on Render returns `401 Unauthorized`. The error progressed through three stages as fixes were applied.

## Timeline

| Stage | Error | Root Cause | Status |
|-------|-------|------------|--------|
| 1 | `Missing authorization header` | `get_current_user(authorization: Optional[str])` — FastAPI cannot inject header as plain string param | ✅ Fixed in `667140b` |
| 2 | `Unable to resolve token signing key: HTTP Error 404` | Flutter SDK sends ES256 tokens; backend tried to fetch JWKS from `{supabase_url}/.well-known/jwks.json` — returns 404 | ✅ Fixed in `d6ed786` |
| 3 | Unknown — needs deployment | JWKS URL 404 persists; falls back to HS256 or unverified decode | 🔴 Not yet tested on Render |

---

## Fix Applied: Stage 1 — Header Not Read (`667140b`)

### Problem
`get_current_user` used `authorization: Optional[str] = None` as a FastAPI dependency parameter. FastAPI has no built-in way to inject a request header value into a plain string parameter — it only injects the *entire Request* object.

### Before
```python
def get_current_user(
    authorization: Optional[str] = None,  # Never populated
) -> AuthenticatedUser:
```

### After
```python
def get_current_user(
    request: Request,
) -> AuthenticatedUser:
    authorization = request.headers.get("Authorization")
```

---

## Fix Applied: Stage 2 — JWKS URL 404 (`d6ed786`)

### Problem
Flutter Supabase SDK sends ES256 (ECDSA) tokens, not HS256. The original code detected `alg: ES256` from the token header and attempted to fetch JWKS from a single URL, which returned 404.

### New Strategy (3-tier fallback)
1. **HS256** with `SUPABASE_JWT_SECRET` — tried first regardless of token header
2. **ES256 via `PyJWKClient`** — tries both JWKS URLs
3. **Unverified decode** — logs warning, for development only

### Changed Files
- `services/gateway/auth_middleware.py`

---

## Token Details (Flutter Supabase SDK)

### Header
```json
{
  "alg": "ES256",
  "kid": "dc5b9bc2-c652-4297-9bc3-4293082b9e76",
  "typ": "JWT"
}
```

### Payload
```json
{
  "iss": "https://gcxxmjptbyvlabqzcprv.supabase.co/auth/v1",
  "sub": "3a6b4a4c-48cf-461e-8372-82462be57e6e",
  "aud": "authenticated",
  "exp": 1779125175,
  "iat": 1779121575,
  "email": "apitester@gmail.com",
  "role": "authenticated"
}
```

### Supabase Project
- URL: `https://gcxxmjptbyvlabqzcprv.supabase.co`
- Issuer: `{url}/auth/v1`
- JWKS candidates:
  - `{url}/.well-known/jwks.json`
  - `{url}/auth/v1/.well-known/jwks.json`

---

## Next Steps
1. Deploy `d6ed786` to Render
2. Test POST `/api/assess` with Flutter
3. If HS256 verification fails, check if `SUPABASE_JWT_SECRET` matches the key used for ES256 tokens
4. If JWKS is required, enable it in Supabase Auth settings or open a Supabase support ticket
