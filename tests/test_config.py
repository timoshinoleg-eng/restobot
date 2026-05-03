# tests/test_config.py
"""Tests for application configuration."""

from datetime import datetime, timezone

import pytest

from shared.config import get_settings
from shared.jwt_utils import create_access_token, verify_access_token


class TestSettings:
    """Test settings validation."""

    def test_get_tenant_schema_valid(self) -> None:
        """Test tenant schema generation."""
        settings = get_settings()
        schema = settings.get_tenant_schema("abc123")
        assert schema == "tenant_abc123"  # nosec B101

    def test_get_tenant_schema_invalid(self) -> None:
        """Test that invalid tenant IDs raise ValueError."""
        settings = get_settings()
        with pytest.raises(ValueError):
            settings.get_tenant_schema("abc; DROP TABLE users; --")

    def test_settings_cached(self) -> None:
        """Test that get_settings returns cached instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2  # nosec B101

    def test_jwt_timestamps_are_unix_seconds(self) -> None:
        """JWT creation should emit numeric timestamps accepted by jose."""
        token = create_access_token(user_id=1, tenant_id="demo")

        payload = verify_access_token(token)

        assert payload is not None  # nosec B101
        assert isinstance(payload.iat, datetime)  # nosec B101
        assert isinstance(payload.exp, datetime)  # nosec B101
        assert payload.iat.tzinfo == timezone.utc  # nosec B101
        assert payload.exp.tzinfo == timezone.utc  # nosec B101
        assert payload.exp > payload.iat  # nosec B101
