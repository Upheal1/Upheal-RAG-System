"""
Auth middleware for JWT validation using Supabase.
"""

from __future__ import annotations

import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from services.shared.logging import get_logger


class AuthenticatedUser(BaseModel):
    """Represents an authenticated user from JWT token."""

    user_id: str
    email: Optional[str] = None
    exp: Optional[int] = None


_JWT_SECRET_ENV = "SUPABASE_JWT_SECRET"
_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def _get_jwt_secret() -> str:
    """Get JWT secret from environment, with fallback for testing."""
    secret = os.getenv(_JWT_SECRET_ENV)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: JWT secret not set",
        )
    return secret


def _get_jwks_url() -> str:
    """Build the Supabase JWKS URL used for ES256 token verification."""
    supabase_url = os.getenv(
        "UPHEAL_SUPABASE_URL",
        "https://gcxxmjptbyvlabqzcprv.supabase.co",
    ).rstrip("/")
    return f"{supabase_url}/.well-known/jwks.json"


def _get_jwks_client(jwks_url: Optional[str] = None) -> PyJWKClient:
    """Return a cached PyJWT JWKS client for Supabase signing key lookup."""
    url = jwks_url or _get_jwks_url()
    if url not in _JWKS_CLIENTS:
        _JWKS_CLIENTS[url] = PyJWKClient(url)
    return _JWKS_CLIENTS[url]


def _get_es256_signing_key(token: str):
    """Resolve the ES256 signing key that matches the JWT header kid."""
    try:
        return _get_jwks_client().get_signing_key_from_jwt(token).key
    except PyJWKClientError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to resolve token signing key: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _decode_token(token: str) -> dict:
    """Decode and validate JWT token. Supports both HS256 and ES256."""
    
    # First, try to decode header to determine algorithm
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")
    except Exception:
        algorithm = "HS256"
    
    try:
        if algorithm == "ES256":
            signing_key = _get_es256_signing_key(token)
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )
            return payload

        secret = _get_jwt_secret()
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
