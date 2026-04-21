# tests/test_bot.py
"""Tests for Telegram bot."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, User

from bot.main import UserFlow, _check_rate_limit


class TestRateLimitHelper:
    """Test bot rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self) -> None:
        """Should allow request under limit."""
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=User)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        with patch("shared.rate_limiter.get_redis", return_value=mock_redis):
            result = await _check_rate_limit(message)
        assert result is True  # nosec B101

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self) -> None:
        """Should block request over limit."""
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=User)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "5"
        with patch("shared.rate_limiter.get_redis", return_value=mock_redis):
            result = await _check_rate_limit(message)
        assert result is False  # nosec B101
        message.answer.assert_awaited_once()


class TestFSMStates:
    """Test FSM state definitions."""

    def test_states_defined(self) -> None:
        """All required states should exist."""
        assert UserFlow.ai_recommend is not None  # nosec B101
        assert UserFlow.order_type is not None  # nosec B101
