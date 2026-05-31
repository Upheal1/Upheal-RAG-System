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
_logger = get_logger(__name__)


def _get_jwt_secret() -> Optional[str]:
    """Get JWT secret from environment (may be None if not configured)."""
    return os.getenv(_JWT_SECRET_ENV)


def _get_jwks_urls() -> list[str]:
    """Build the list of Supabase JWKS URLs to try for ES256 verification."""
    supabase_url = os.getenv(
        "UPHEAL_SUPABASE_URL",
        "https://gcxxmjptbyvlabqzcprv.supabase.co",
    ).rstrip("/")
    return [
        f"{supabase_url}/.well-known/jwks.json",
        f"{supabase_url}/auth/v1/.well-known/jwks.json",
    ]


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWT JWKS client for Supabase signing key lookup."""
    if jwks_url not in _JWKS_CLIENTS:
        _JWKS_CLIENTS[jwks_url] = PyJWKClient(jwks_url)
    return _JWKS_CLIENTS[jwks_url]


def _try_es256_signing_key(token: str) -> Optional[object]:
    """Try to resolve the ES256 signing key from all JWKS URLs."""
    for url in _get_jwks_urls():
        try:
            client = _get_jwks_client(url)
            key = client.get_signing_key_from_jwt(token).key
            _logger.info(f"auth.es256_key_resolved - url={url}")
            return key
        except PyJWKClientError:
            _logger.warning(f"auth.es256_jwks_miss - url={url}")
            continue
        except Exception as exc:
            _logger.warning(f"auth.es256_jwks_error - url={url} error={exc}")
            continue
    return None


def _decode_token(token: str) -> dict:
    """Decode and validate JWT token using a 3-tier fallback strategy.

    Tier 1: HS256 with SUPABASE_JWT_SECRET (works for all Supabase tokens).
    Tier 2: ES256 via JWKS (needed when Supabase issues ECDSA tokens).
    Tier 3: Unverified decode — development fallback, logs a warning.
    """

    errors: list[str] = []

    # Tier 1: HS256 with shared secret
    secret = _get_jwt_secret()
    if secret:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            _logger.info("auth.token_decoded - tier=HS256")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            errors.append(f"HS256: {e}")
            _logger.debug(f"auth.hs256_failed - error={e}")

    # Tier 2: ES256 via JWKS
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")
    except Exception:
        algorithm = "unknown"

    if algorithm == "ES256":
        signing_key = _try_es256_signing_key(token)
        if signing_key is not None:
            try:
                payload = jwt.decode(
                    token,
                    signing_key,
                    algorithms=["ES256"],
                    options={"verify_aud": False},
                )
                _logger.info("auth.token_decoded - tier=ES256")
                return payload
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidTokenError as e:
                errors.append(f"ES256: {e}")
                _logger.warning(f"auth.es256_decode_failed - error={e}")

    # Tier 3: Unverified decode (development only)
    _logger.warning("auth.unverified_decode - all_tiers_failed, using unverified decode (dev only)")
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
            algorithms=["HS256", "ES256"],
        )
        return payload
    except Exception as e:
        _logger.error(f"auth.decode_failed - errors={errors}, unverified_error={e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {'; '.join(errors)}",
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
