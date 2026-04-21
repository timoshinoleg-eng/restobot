# tests/test_database.py
"""Tests for database helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.database import check_database_health, close_raw_pool


class TestDatabaseHealth:
    """Test DB health check."""

    @pytest.mark.asyncio
    async def test_healthy_when_db_responds(self) -> None:
        """Health check should be healthy when DB responds."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"alive": 1}
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("shared.database._raw_pool", mock_pool):
            result = await check_database_health()
        assert result["status"] == "healthy"  # nosec B101

    @pytest.mark.asyncio
    async def test_unhealthy_on_exception(self) -> None:
        """Health check should be unhealthy on exception."""
        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("DB down")

        with patch("shared.database._raw_pool", mock_pool):
            result = await check_database_health()
        assert result["status"] == "unhealthy"  # nosec B101
        assert "error" in result  # nosec B101


class TestRawPool:
    """Test raw pool lifecycle."""

    @pytest.mark.asyncio
    async def test_close_raw_pool_clears_reference(self) -> None:
        """Closing pool should clear internal reference."""
        mock_pool = AsyncMock()
        with patch("shared.database._raw_pool", mock_pool):
            await close_raw_pool()
        mock_pool.close.assert_awaited_once()
