# tests/test_sql_utils.py
"""Tests for SQL utilities."""

import pytest

from shared.sql_utils import format_sql


class TestFormatSql:
    """Test safe SQL formatter."""

    def test_valid_schema(self) -> None:
        """Test formatting with valid schema name."""
        result = format_sql("SELECT * FROM {}.table", "tenant_123")
        assert result == "SELECT * FROM tenant_123.table"  # nosec B101

    def test_multiple_schemas(self) -> None:
        """Test formatting with multiple schema placeholders."""
        result = format_sql(
            "SELECT * FROM {}.t1 JOIN {}.t2",
            "tenant_1",
            "tenant_2",
        )
        assert result == "SELECT * FROM tenant_1.t1 JOIN tenant_2.t2"  # nosec B101

    def test_invalid_schema_rejected(self) -> None:
        """Test that invalid schema names raise ValueError."""
        with pytest.raises(ValueError):
            format_sql("SELECT * FROM {}.table", "tenant; DROP TABLE users; --")

    def test_empty_schema_rejected(self) -> None:
        """Test that empty schema name is rejected."""
        with pytest.raises(ValueError):
            format_sql("SELECT * FROM {}.table", "")
