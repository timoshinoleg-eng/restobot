# tests/test_bot_commands.py
"""Tests for bot command handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, User

from bot.main import cmd_help, cmd_support


class TestBotCommands:
    """Test simple bot commands."""

    @pytest.fixture
    def message(self) -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = 123
        msg.answer = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_cmd_help(self, message: Message) -> None:
        """Help command should send help text."""
        mock_state = AsyncMock()
        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_help(message, mock_state)
        message.answer.assert_awaited_once()  # type: ignore[attr-defined]
        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "/start" in call_args  # nosec B101

    @pytest.mark.asyncio
    async def test_cmd_support(self, message: Message) -> None:
        """Support command should send support info."""
        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_support(message)
        message.answer.assert_awaited_once()  # type: ignore[attr-defined]
        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "support@restobot.ru" in call_args  # nosec B101
