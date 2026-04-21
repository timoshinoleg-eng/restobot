# tests/test_logging.py
"""Tests for structured logging configuration."""

import logging

from shared.logging_config import configure_logging


class TestLoggingConfig:
    """Test logging setup."""

    def test_configure_logging_does_not_raise(self) -> None:
        """Configuring logging should complete without errors."""
        configure_logging()
        logger = logging.getLogger()
        assert len(logger.handlers) > 0  # nosec B101
