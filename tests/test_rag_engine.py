# tests/test_rag_engine.py
"""Tests for RAG engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.rag_engine import CircuitBreaker, FallbackEngine, RAGEngine


class TestCircuitBreaker:
    """Test circuit breaker logic."""

    def test_initially_closed(self) -> None:
        """Circuit should start closed."""
        cb = CircuitBreaker()
        assert cb.can_execute() is True  # nosec B101

    def test_opens_after_threshold(self) -> None:
        """Circuit should open after failure threshold."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.can_execute() is False  # nosec B101

    def test_closes_after_success(self) -> None:
        """Circuit should close after success."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        cb.record_success()
        assert cb.can_execute() is True  # nosec B101


class TestFallbackEngine:
    """Test fallback formatter."""

    def test_format_recommendation(self) -> None:
        """Fallback should format dishes into markdown."""
        dishes = [
            {"name": "Pizza", "price": 500.0, "description": "Tasty pizza"},
        ]
        result = FallbackEngine.format_recommendation(dishes, 500.0)
        assert "Pizza" in result  # nosec B101
        assert "500" in result  # nosec B101


class TestRAGEngine:
    """Test RAG engine with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_recommend_uses_fallback_when_ai_down(self) -> None:
        """RAG should use fallback when YandexGPT is unavailable."""
        engine = RAGEngine()
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])

        with patch.object(engine.ygpt, "embed", AsyncMock(side_effect=RuntimeError("AI down"))):
            with patch("ai.rag_engine.get_raw_pool", return_value=mock_pool):
                with patch("ai.rag_engine.settings.AI_FALLBACK_ENABLED", True):
                    result = await engine.recommend(
                        tenant_schema="tenant_test",
                        tenant_id="test",
                        query="pizza",
                    )

        assert result["source"] == "fallback"  # nosec B101
