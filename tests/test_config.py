# tests/test_config.py
"""Tests for application configuration."""

import pytest

from shared.config import get_settings


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
