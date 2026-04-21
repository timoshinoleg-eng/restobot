# tests/test_rate_limiter.py
"""Tests for rate limiter."""

from unittest.mock import AsyncMock, patch

import pytest

from shared.rate_limiter import RateLimiter


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(limit=3, window=60)


class TestRateLimiter:
    """Test Redis-backed rate limiter."""

    @pytest.mark.asyncio
    async def test_allowed_when_no_key(self, limiter: RateLimiter) -> None:
        """Test request is allowed when no key exists."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        with patch("shared.rate_limiter.get_redis", return_value=mock_redis):
            assert await limiter.is_allowed(1) is True  # nosec B101
            mock_redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_denied_when_limit_reached(self, limiter: RateLimiter) -> None:
        """Test request is denied when limit reached."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "3"
        with patch("shared.rate_limiter.get_redis", return_value=mock_redis):
            assert await limiter.is_allowed(1) is False  # nosec B101

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self, limiter: RateLimiter) -> None:
        """Test fail-open behavior when Redis is unavailable."""
        with patch("shared.rate_limiter.get_redis", side_effect=Exception("Redis down")):
            assert await limiter.is_allowed(1) is True  # nosec B101

    @pytest.mark.asyncio
    async def test_remaining_count(self, limiter: RateLimiter) -> None:
        """Test remaining requests calculation."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "1"
        with patch("shared.rate_limiter.get_redis", return_value=mock_redis):
            assert await limiter.remaining(1) == 2  # nosec B101
