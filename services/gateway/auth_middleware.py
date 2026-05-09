"""
Supabase JWT Authentication Middleware

Validates JWT tokens from Supabase Auth and extracts user identity.
Protects API endpoints requiring authentication.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from services.shared.logging import get_logger

logger = get_logger(__name__)

# JWT Configuration
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("UPHEAL_SUPABASE_URL", "https://gcxxmjptbyvlabqzcprv.supabase.co")
ALGORITHM = "HS256"

# Security scheme for FastAPI docs
security_bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Authenticated user context extracted from JWT."""
    
    user_id: UUID
    email: Optional[str] = None
    app_metadata: Dict = {}
    user_metadata: Dict = {}
    role: str = "authenticated"
    
    model_config = {"frozen": True}


class JWTValidator:
    """
    Validates Supabase JWT tokens.
    
    Supports both Supabase-issued tokens (with 'sub' claim)
    and custom verification against the Supabase project secret.
    """
    
    def __init__(self, jwt_secret: Optional[str] = None):
        self.jwt_secret = jwt_secret or SUPABASE_JWT_SECRET
        
    def validate_token(self, token: str) -> AuthenticatedUser:
        """
        Validate a JWT token and extract user information.
        
        Parameters
        ----------
        token : str
            The JWT token from the Authorization header
            
        Returns
        -------
        AuthenticatedUser
            User context extracted from token
            
        Raises
        ------
        HTTPException
            If token is invalid or expired
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        try:
            # Decode the JWT
            # Note: In production, Supabase uses asymmetric keys (RS256)
            # For development, we can use the JWT secret
            if self.jwt_secret:
                payload = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=[ALGORITHM],
                    options={"verify_aud": False},
                )
            else:
                # Development mode: decode without verification
                # WARNING: Only for local development!
                payload = jwt.decode(
                    token,
                    "",
                    algorithms=[ALGORITHM],
                    options={"verify_signature": False, "verify_aud": False},
                )
                logger.warning("jwt.validate.no_secret", 
                              message="JWT validation without secret - development mode only")
            
            # Extract user ID from 'sub' claim (standard JWT subject)
            user_id_str = payload.get("sub")
            if not user_id_str:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID",
                )
            
            try:
                user_id = UUID(user_id_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: malformed user ID",
                )
            
            return AuthenticatedUser(
                user_id=user_id,
                email=payload.get("email"),
                app_metadata=payload.get("app_metadata", {}),
                user_metadata=payload.get("user_metadata", {}),
                role=payload.get("role", "authenticated"),
            )
            
        except JWTError as e:
            logger.warning("jwt.validate.failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error("jwt.validate.error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )


# Global validator instance
_validator: Optional[JWTValidator] = None


def get_validator() -> JWTValidator:
    """Get or create the global JWT validator."""
    global _validator
    if _validator is None:
        _validator = JWTValidator()
    return _validator


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> AuthenticatedUser:
    """
    Dependency to extract and validate the current user from JWT.
    
    Usage in FastAPI endpoints:
        @app.get("/protected")
        def protected_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
            return {"user_id": user.user_id}
    
    Parameters
    ----------
    request : Request
        FastAPI request object
    credentials : HTTPAuthorizationCredentials, optional
        Bearer token from Authorization header
        
    Returns
    -------
    AuthenticatedUser
        Validated user context
    """
    # Try to get token from credentials first
    token = None
    if credentials:
        token = credentials.credentials
    else:
        # Fallback to header extraction
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    validator = get_validator()
    return validator.validate_token(token)


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[AuthenticatedUser]:
    """
    Optional authentication - returns user if token valid, None otherwise.
    
    Use for endpoints that work with or without authentication.
    """
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


class AuthMiddleware:
    """
    FastAPI middleware for authentication.
    
    Applies JWT validation to protected routes.
    """
    
    def __init__(
        self,
        protected_paths: Optional[List[str]] = None,
        excluded_paths: Optional[List[str]] = None,
    ):
        """
        Initialize middleware.
        
        Parameters
        ----------
        protected_paths : List[str], optional
            Paths that require authentication (e.g., ["/api/"])
        excluded_paths : List[str], optional
            Paths that are always public (e.g., ["/health", "/docs"])
        """
        self.protected_paths = protected_paths or ["/api/"]
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        self.validator = get_validator()
    
    async def __call__(self, request: Request, call_next):
        """
        Process request through authentication middleware.
        
        This is designed to work as a FastAPI middleware.
        """
        path = request.url.path
        
        # Check if path should be excluded
        for excluded in self.excluded_paths:
            if path.startswith(excluded):
                return await call_next(request)
        
        # Check if path requires protection
        requires_auth = any(path.startswith(protected) for protected in self.protected_paths)
        
        if requires_auth:
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            try:
                user = self.validator.validate_token(auth_header)
                # Store user in request state for access in endpoints
                request.state.user = user
                logger.debug("auth.middleware.success", user_id=str(user.user_id), path=path)
            except HTTPException:
                raise
            except Exception as e:
                logger.error("auth.middleware.error", error=str(e), path=path)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed",
                )
        
        return await call_next(request)


def require_auth():
    """
    Decorator-like dependency for requiring authentication.
    
    Usage:
        @app.get("/api/protected")
        async def endpoint(user: AuthenticatedUser = Depends(require_auth())):
            pass
    """
    return get_current_user


# Convenience function for testing
def create_test_user(user_id: Optional[str] = None) -> AuthenticatedUser:
    """Create a test user for development/testing."""
    from uuid import uuid4
    return AuthenticatedUser(
        user_id=UUID(user_id) if user_id else uuid4(),
        email="test@example.com",
        role="authenticated",
    )
