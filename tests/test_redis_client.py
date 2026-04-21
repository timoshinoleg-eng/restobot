# tests/test_redis_client.py
"""Tests for shared Redis client."""

from unittest.mock import AsyncMock, patch

import pytest

from shared.redis_client import get_cache, set_cache


class TestRedisCache:
    """Test Redis caching helpers."""

    @pytest.mark.asyncio
    async def test_get_cache_returns_none_when_empty(self) -> None:
        """get_cache should return None when key missing."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        with patch("shared.redis_client.get_redis", return_value=mock_redis):
            result = await get_cache("test_key")
        assert result is None  # nosec B101

    @pytest.mark.asyncio
    async def test_get_cache_returns_parsed_json(self) -> None:
        """get_cache should parse JSON from Redis."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "[1, 2, 3]"
        with patch("shared.redis_client.get_redis", return_value=mock_redis):
            result = await get_cache("test_key")
        assert result == [1, 2, 3]  # nosec B101

    @pytest.mark.asyncio
    async def test_set_cache_stores_json(self) -> None:
        """set_cache should store JSON with TTL."""
        mock_redis = AsyncMock()
        with patch("shared.redis_client.get_redis", return_value=mock_redis):
            await set_cache("test_key", {"a": 1}, ttl=60)
        mock_redis.setex.assert_awaited_once()
