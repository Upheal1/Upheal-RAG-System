# Backend Authorization Header Issue Analysis

## Issue Summary
Based on the BACKEND_ISSUE_REPORT.md and codebase analysis, the authorization header issue where the Flutter frontend was sending the `Authorization: Bearer <token>` header correctly but the `/api/assess` endpoint was returning `401 Missing authorization header` has already been resolved.

## Root Causes That Were Fixed

### 1. Missing Request Parameter in get_current_user
**Location**: `services/gateway/auth_middleware.py` (lines 114-116)
**Problem**: The `get_current_user` function originally expected an `authorization` parameter that FastAPI couldn't automatically inject.
**Fix Applied**: Changed to use `request: Request` and extract header from request:
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

### 2. ES256 Token Support
**Location**: `services/gateway/auth_middleware.py` (lines 61-112)
**Problem**: The Flutter Supabase SDK sends ES256 (ECDSA) tokens, but the backend only supported HS256.
**Fix Applied**: Added JWKS fetching from Supabase to support ES256:
```python
def _decode_token(token: str) -> dict:
    # Detect algorithm from token header
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg", "HS256")
    
    if algorithm == "ES256":
        # Fetch JWKS from Supabase for verification
        jwks = _get_jwks()
        payload = jwt.decode(token, jwks, algorithms=["ES256"], options={"verify_aud": False})
    else:
        # HS256 with JWT secret
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
```

## Current Code Status
After examining the current codebase:

1. **auth_middleware.py** contains both fixes:
   - Proper request-based header extraction (line 124)
   - ES256/JWKS support (lines 61-112)

2. **Main application** (`services/gateway/main.py`) correctly uses the dependency:
   - Line 176: `user: AuthenticatedUser = Depends(get_current_user)`
   - Line 210: Same for roadmap endpoint

3. **Environment configuration** includes the JWT secret:
   - `SUPABASE_JWT_SECRET=dc5b9bc2-c652-4297-9bc3-4293082b9e76` in deployments/upheal-rag.env

## Potential Remaining Issues to Check

While the described fixes are in place, here are areas to verify if issues persist:

### 1. Middleware Order
Verify that authentication middleware runs before any route handlers that might interfere:
- Check if any custom middleware could be stripping headers
- Confirm CORS middleware is properly configured (lines 46-52 in main.py)

### 2. Proxy/Load Balancer Issues
Since the app is deployed on Render:
- Ensure Render isn't stripping Authorization headers
- Check if any transformation rules or middleware on Render could affect headers
- Verify that the `www-authenticate: Bearer` header in responses indicates the auth middleware is running

### 3. Token Validation Logic
Double-check the token validation:
- Ensure the JWT secret in environment matches what Supabase uses
- Verify that the JWKS endpoint is accessible from the Render environment
- Check that token expiration handling is working correctly

### 4. Route Specific Issues
Verify the `/api/assess` endpoint specifically:
- Confirm it's not being overridden by another route
- Check that the dependency injection is working correctly
- Ensure no exception handling is masking the real error

## Recommended Verification Steps

1. **Deploy the current code** to Render (if not already done)
2. **Test with a simple curl command** to isolate the issue:
   ```bash
   curl -X POST https://upheal-rag.onrender.com/api/assess \
     -H "Authorization: Bearer <valid_token>" \
     -H "Content-Type: application/json" \
     -d '{"answers": {"gad7_q1": 0}, "user_id": "test-user"}'
   ```
3. **Check logs** on Render for any authentication-related warnings
4. **Verify environment variables** are properly set in the Render deployment
5. **Test the health endpoint** to ensure basic connectivity:
   ```bash
   curl https://upheal-rag.onrender.com/health
   ```

## Conclusion
Based on the code analysis, the authorization header issue described in BACKEND_ISSUE_REPORT.md has been properly fixed in the current codebase. If the issue persists in production, it's likely related to:
1. Deployment not having the latest code
2. Environment configuration differences between local and production
3. Platform-specific issues on Render (proxy, load balancer, etc.)
4. Token generation or validation issues specific to the production environment

The fixes applied to `auth_middleware.py` correctly address both the missing request parameter issue and the ES256 token support requirement.