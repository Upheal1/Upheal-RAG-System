import os
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from services.gateway.auth_middleware import (
    AuthenticatedUser,
    get_current_user,
    _get_jwt_secret,
    _decode_token,
)


TEST_SECRET = "test-jwt-secret-key-12345678901234567890"


def create_test_token(
    sub: str,
    email: str = "test@example.com",
    expired: bool = False,
    secret: str = TEST_SECRET,
) -> str:
    """Create a valid JWT token for testing."""
    exp = int(time.time()) - 3600 if expired else int(time.time()) + 3600
    payload = {"sub": sub, "email": email, "exp": exp}
    return jwt.encode(payload, secret, algorithm="HS256")


class TestGetJwtSecret:
    def test_returns_secret_when_set(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}):
            secret = _get_jwt_secret()
            assert secret == TEST_SECRET

    def test_raises_when_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                _get_jwt_secret()
            assert exc_info.value.status_code == 500
            assert "JWT secret not set" in exc_info.value.detail


class TestDecodeToken:
    @pytest.fixture(autouse=True)
    def setup_env(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}):
            yield

    def test_valid_token_returns_payload(self) -> None:
        token = create_test_token("user-123", "test@example.com")
        payload = _decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"

    def test_expired_token_raises_401(self) -> None:
        token = create_test_token("user-123", expired=True)
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_invalid_token_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _decode_token("invalid.token.here")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_token_without_sub_raises_401(self) -> None:
        payload = {"email": "test@example.com", "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(f"Bearer {token}")
        assert exc_info.value.status_code == 401
        assert "sub" in exc_info.value.detail.lower()


class TestGetCurrentUser:
    @pytest.fixture(autouse=True)
    def setup_env(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}):
            yield

    def test_missing_auth_header_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(None)
        assert exc_info.value.status_code == 401
        assert "Missing authorization header" in exc_info.value.detail

    def test_invalid_format_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("InvalidToken")
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    def test_non_bearer_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("Basic sometoken")
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    def test_valid_token_returns_authenticated_user(self) -> None:
        token = create_test_token("user-abc-123", "user@test.com")
        user = get_current_user(f"Bearer {token}")
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "user-abc-123"
        assert user.email == "user@test.com"

    def test_token_without_email_returns_none(self) -> None:
        payload = {"sub": "user-no-email", "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        user = get_current_user(f"Bearer {token}")
        assert user.user_id == "user-no-email"
        assert user.email is None


class TestAuthenticatedUser:
    def test_model_validation(self) -> None:
        user = AuthenticatedUser(
            user_id="test-123", email="test@test.com", exp=1234567890
        )
        assert user.user_id == "test-123"
        assert user.email == "test@test.com"
        assert user.exp == 1234567890

    def test_optional_fields(self) -> None:
        user = AuthenticatedUser(user_id="test-123")
        assert user.user_id == "test-123"
        assert user.email is None
        assert user.exp is None
