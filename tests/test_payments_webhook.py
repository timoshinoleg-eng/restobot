# tests/test_payments_webhook.py
"""Tests for payment webhook handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from payments.worker import PaymentWorker


class TestPaymentWebhook:
    """Test webhook processing."""

    @pytest.fixture
    def worker(self) -> PaymentWorker:
        return PaymentWorker()

    @pytest.mark.asyncio
    async def test_handle_webhook_payment_succeeded(self, worker: PaymentWorker) -> None:
        """Should update order and accrue loyalty on success."""
        mock_order = {
            "id": 1,
            "order_number": "R-001",
            "user_id": 10,
            "loyalty_used": 0,
            "payment_status": "pending",
        }

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_order)
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("payments.worker.settings.YOOKASSA_ENABLED", True):
            with patch("payments.worker._ensure_yookassa_config"):
                with patch("payments.worker.get_raw_pool", return_value=mock_pool):
                    with patch("payments.worker.send_order_status_update", new_callable=AsyncMock):
                        await worker.handle_webhook(
                            "tenant_test",
                            {"object": {"id": "pay_123"}, "event": "payment.succeeded"},
                        )

        assert mock_conn.execute.await_count == 2  # nosec B101
        mock_conn.fetchval.assert_awaited_once()  # nosec B101

    @pytest.mark.asyncio
    async def test_handle_webhook_payment_cancelled(self, worker: PaymentWorker) -> None:
        """Should refund loyalty and cancel order."""
        mock_order = {
            "id": 1,
            "order_number": "R-001",
            "user_id": 10,
            "loyalty_used": 50.0,
            "payment_status": "pending",
        }

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_order)
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("payments.worker.settings.YOOKASSA_ENABLED", True):
            with patch("payments.worker._ensure_yookassa_config"):
                with patch("payments.worker.get_raw_pool", return_value=mock_pool):
                    with patch("payments.worker.send_order_status_update", new_callable=AsyncMock):
                        await worker.handle_webhook(
                            "tenant_test",
                            {"object": {"id": "pay_123"}, "event": "payment.canceled"},
                        )

        assert mock_conn.execute.await_count == 2  # nosec B101
        mock_conn.fetchval.assert_awaited_once()  # nosec B101
