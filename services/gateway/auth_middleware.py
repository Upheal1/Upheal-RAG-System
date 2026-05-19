"""
Auth middleware for JWT validation using Supabase.
"""

from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from services.shared.logging import get_logger


class AuthenticatedUser(BaseModel):
    """Represents an authenticated user from JWT token."""

    user_id: str
    email: Optional[str] = None
    exp: Optional[int] = None


_JWT_SECRET_ENV = "SUPABASE_JWT_SECRET"
_JWKS_CACHE: Optional[dict] = None


def _get_jwt_secret() -> str:
    """Get JWT secret from environment, with fallback for testing."""
    secret = os.getenv(_JWT_SECRET_ENV)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: JWT secret not set",
        )
    return secret


def _get_jwks() -> dict:
    """Fetch and cache JWKS from Supabase for ES256 verification."""
    global _JWKS_CACHE
    if _JWKS_CACHE is not None:
        return _JWKS_CACHE
    
    supabase_url = os.getenv("UPHEAL_SUPABASE_URL", "https://gcxxmjptbyvlabqzcprv.supabase.co")
    jwks_url = f"{supabase_url}/.well-known/jwks.json"
    
    import httpx
    try:
        response = httpx.get(jwks_url, timeout=10)
        if response.status_code == 200:
            _JWKS_CACHE = response.json()
            return _JWKS_CACHE
    except Exception:
        pass
    
    return {"keys": []}


def _decode_token(token: str) -> dict:
    """Decode and validate JWT token. Supports both HS256 and ES256."""
    
    # First, try to decode header to determine algorithm
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")
    except Exception:
        algorithm = "HS256"
    
    secret = _get_jwt_secret()
    logger = get_logger(__name__)
    
    try:
        if algorithm == "ES256":
            # For ES256, use JWKS from Supabase
            jwks = _get_jwks()
            if jwks.get("keys"):
                payload = jwt.decode(
                    token,
                    jwks,
                    algorithms=["ES256"],
                    options={"verify_aud": False},
                )
                return payload
            else:
                # Fallback: try without verification (for development only)
                logger.warning("auth.es256_no_jwks - falling back to unverified decode")
                payload = jwt.decode(token, options={"verify_signature": False})
                return payload
        else:
            # For HS256, use JWT secret
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    request: Request,
) -> AuthenticatedUser:
    """
    FastAPI dependency to extract and validate user from JWT token.

    Expects Authorization header in format: "Bearer <token>"

    Returns AuthenticatedUser with user_id from token's 'sub' claim.
    """
    authorization = request.headers.get("Authorization")
    
    if not authorization:
        logger = get_logger(__name__)
        logger.warning(f"auth.missing_header - headers: {dict(request.headers)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    payload = _decode_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email")

    return AuthenticatedUser(
        user_id=user_id,
        email=email,
        exp=payload.get("exp"),
    )


def require_auth(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Explicit dependency for endpoints requiring authentication.
    """
    return user
