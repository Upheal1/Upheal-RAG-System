import os
import time
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import jwt
import pytest
from fastapi import HTTPException

from services.gateway.auth_middleware import (
    AuthenticatedUser,
    _decode_token,
    _get_jwt_secret,
    _get_jwks_urls,
    _try_es256_signing_key,
    get_current_user,
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


def make_request(authorization: str | None = None):
    headers = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    return SimpleNamespace(headers=headers)


ES256_TOKEN = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6InRlc3Qtc3VwYWJhc2Uta2V5IiwidHlwIjoiSldUIn0"
    ".eyJzdWIiOiJzdXBhYmFzZS11c2VyLTEyMyIsImVtYWlsIjoic3VwYWJhc2VAZXhhbXBsZS5jb20ifQ"
    ".c2lnbmF0dXJl"
)


class TestGetJwtSecret:
    def test_returns_secret_when_set(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}):
            secret = _get_jwt_secret()
            assert secret == TEST_SECRET

    def test_returns_none_when_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            secret = _get_jwt_secret()
            assert secret is None


class TestGetJwksUrls:
    def test_returns_two_urls(self) -> None:
        urls = _get_jwks_urls()
        assert len(urls) == 2
        assert urls[0].endswith("/.well-known/jwks.json")
        assert urls[1].endswith("/auth/v1/.well-known/jwks.json")

    def test_uses_env_var(self) -> None:
        with patch.dict(os.environ, {"UPHEAL_SUPABASE_URL": "https://example.supabase.co"}):
            urls = _get_jwks_urls()
        assert urls[0] == "https://example.supabase.co/.well-known/jwks.json"
        assert urls[1] == "https://example.supabase.co/auth/v1/.well-known/jwks.json"


class TestTryEs256SigningKey:
    def test_returns_key_from_first_url(self) -> None:
        mock_key = MagicMock()
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value.key = mock_key
        with patch(
            "services.gateway.auth_middleware._get_jwks_client",
            return_value=mock_client,
        ):
            result = _try_es256_signing_key(ES256_TOKEN)
        assert result is mock_key

    def test_tries_second_url_on_failure(self) -> None:
        mock_key = MagicMock()
        client_first = MagicMock()
        client_first.get_signing_key_from_jwt.side_effect = Exception("404")
        client_second = MagicMock()
        client_second.get_signing_key_from_jwt.return_value.key = mock_key

        call_count = 0

        def fake_get_jwks_client(url: str):
            nonlocal call_count
            call_count += 1
            return client_first if call_count == 1 else client_second

        with patch(
            "services.gateway.auth_middleware._get_jwks_client",
            side_effect=fake_get_jwks_client,
        ):
            result = _try_es256_signing_key(ES256_TOKEN)
        assert result is mock_key

    def test_returns_none_when_all_urls_fail(self) -> None:
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.side_effect = Exception("404")
        with patch(
            "services.gateway.auth_middleware._get_jwks_client",
            return_value=mock_client,
        ):
            result = _try_es256_signing_key(ES256_TOKEN)
        assert result is None


class TestDecodeToken:
    @pytest.fixture(autouse=True)
    def setup_env(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}):
            yield

    def test_tier1_hs256_valid_token(self) -> None:
        token = create_test_token("user-123", "test@example.com")
        payload = _decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"

    def test_tier1_hs256_expired_token_raises_401(self) -> None:
        token = create_test_token("user-123", expired=True)
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_tier2_es256_uses_jwks_when_hs256_fails(self) -> None:
        payload = {
            "sub": "supabase-user-123",
            "email": "supabase@example.com",
            "exp": int(time.time()) + 3600,
        }
        signing_key = object()

        with patch(
            "services.gateway.auth_middleware._try_es256_signing_key",
            return_value=signing_key,
        ), patch(
            "services.gateway.auth_middleware.jwt.decode",
            return_value=payload,
        ) as mock_decode:
            mock_decode.side_effect = [
                jwt.InvalidTokenError("wrong algorithm"),
                payload,
            ]
            decoded = _decode_token(ES256_TOKEN)

        assert decoded["sub"] == "supabase-user-123"

    def test_tier2_es256_expired_token_raises_401(self) -> None:
        signing_key = object()
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}), patch(
            "services.gateway.auth_middleware._try_es256_signing_key",
            return_value=signing_key,
        ), patch(
            "services.gateway.auth_middleware.jwt.decode",
            side_effect=[
                jwt.InvalidTokenError("HS256 failed"),
                jwt.ExpiredSignatureError(),
            ],
        ):
            with pytest.raises(HTTPException) as exc_info:
                _decode_token(ES256_TOKEN)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_tier3_unverified_decode_fallback(self) -> None:
        token = create_test_token("tier3-user", "tier3@test.com")
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": "wrong-secret"}), patch(
            "services.gateway.auth_middleware._try_es256_signing_key",
            return_value=None,
        ):
            payload = _decode_token(token)

        assert payload["sub"] == "tier3-user"
        assert payload["email"] == "tier3@test.com"

    def test_tier3_completely_invalid_jwt_raises_401(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                _decode_token("not-even-a-jwt")
            assert exc_info.value.status_code == 401

    def test_token_without_sub_raises_401(self) -> None:
        payload = {"email": "test@example.com", "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(make_request(f"Bearer {token}"))
        assert exc_info.value.status_code == 401
        assert "sub" in exc_info.value.detail.lower()


class TestGetCurrentUser:
    @pytest.fixture(autouse=True)
    def setup_env(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": TEST_SECRET}):
            yield

    def test_missing_auth_header_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(make_request())
        assert exc_info.value.status_code == 401
        assert "Missing authorization header" in exc_info.value.detail

    def test_invalid_format_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(make_request("InvalidToken"))
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    def test_non_bearer_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(make_request("Basic sometoken"))
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    def test_valid_token_returns_authenticated_user(self) -> None:
        token = create_test_token("user-abc-123", "user@test.com")
        user = get_current_user(make_request(f"Bearer {token}"))
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "user-abc-123"
        assert user.email == "user@test.com"

    def test_token_without_email_returns_none(self) -> None:
        payload = {"sub": "user-no-email", "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        user = get_current_user(make_request(f"Bearer {token}"))
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