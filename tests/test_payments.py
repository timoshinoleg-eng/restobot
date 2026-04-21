# tests/test_payments.py
"""Tests for payment worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from payments.worker import PaymentWorker


class TestPaymentWorker:
    """Test payment processing worker."""

    @pytest.fixture
    def worker(self) -> PaymentWorker:
        return PaymentWorker()

    @pytest.mark.asyncio
    async def test_process_payment_order_not_found(self, worker: PaymentWorker) -> None:
        """Should raise ValueError when order not found."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("payments.worker.get_raw_pool", return_value=mock_pool):
            with pytest.raises(ValueError, match="not found"):
                await worker.process_payment("tenant_test", 999, "http://return")

    @pytest.mark.asyncio
    async def test_handle_webhook_order_not_found(self, worker: PaymentWorker) -> None:
        """Should log warning when order not found for webhook."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("payments.worker.get_raw_pool", return_value=mock_pool):
            # Should not raise
            await worker.handle_webhook(
                "tenant_test",
                {"object": {"id": "pay_123"}, "event": "payment.succeeded"},
            )

    @pytest.mark.asyncio
    async def test_poll_payment_status_timeout(self, worker: PaymentWorker) -> None:
        """Polling should return False after max attempts."""
        with patch("payments.worker.Payment.find_one") as mock_find:
            mock_find.return_value = MagicMock(status="pending")
            with patch("payments.worker.asyncio.sleep", new_callable=AsyncMock):
                result = await worker.poll_payment_status("tenant_test", "pay_123", 1)
        assert result is False  # nosec B101
