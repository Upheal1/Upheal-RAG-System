from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def _patch_validate_env():
    with patch("services.gateway.main.validate_env"):
        yield
