"""
Auth middleware for JWT validation using Supabase.
"""

from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Represents an authenticated user from JWT token."""

    user_id: str
    email: Optional[str] = None
    exp: Optional[int] = None


_JWT_SECRET_ENV = "SUPABASE_JWT_SECRET"


def _get_jwt_secret() -> str:
    """Get JWT secret from environment, with fallback for testing."""
    secret = os.getenv(_JWT_SECRET_ENV)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: JWT secret not set",
        )
    return secret


def _decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    secret = _get_jwt_secret()
    try:
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
    authorization: Optional[str] = None,
) -> AuthenticatedUser:
    """
    FastAPI dependency to extract and validate user from JWT token.

    Expects Authorization header in format: "Bearer <token>"

    Returns AuthenticatedUser with user_id from token's 'sub' claim.
    """
    if not authorization:
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
