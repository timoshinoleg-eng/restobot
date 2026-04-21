# tests/test_metrics.py
"""Tests for Prometheus metrics."""

from shared.metrics import (
    AI_LATENCY,
    BOT_COMMANDS,
    ORDERS_CREATED,
    PAYMENTS_PROCESSED,
    metrics_endpoint,
)


class TestMetrics:
    """Test metric counters exist and endpoint works."""

    def test_metrics_endpoint_returns_bytes(self) -> None:
        """Metrics endpoint should return bytes."""
        result = metrics_endpoint()
        assert isinstance(result, bytes)  # nosec B101
        assert b"restobot_app_info" in result  # nosec B101

    def test_counters_have_labels(self) -> None:
        """Counters should have expected label names."""
        assert ORDERS_CREATED._labelnames == ("tenant", "type")  # nosec B101
        assert PAYMENTS_PROCESSED._labelnames == ("tenant", "status")  # nosec B101
        assert AI_LATENCY._labelnames == ("tenant", "source")  # nosec B101
        assert BOT_COMMANDS._labelnames == ("command",)  # nosec B101
