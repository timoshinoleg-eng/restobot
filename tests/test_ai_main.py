# tests/test_ai_main.py
"""Tests for AI service entry point."""

from unittest.mock import patch

import pytest

from ai.main import main


class TestAIMain:
    """Test AI service main."""

    @pytest.mark.asyncio
    async def test_main_runs_init_database(self) -> None:
        """Main should call init_database."""
        with patch("ai.main.init_database") as mock_init:
            await main()
        mock_init.assert_awaited_once()
