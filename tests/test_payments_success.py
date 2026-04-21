# tests/test_payments_success.py
"""Tests for successful payment flows."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from payments.worker import PaymentWorker


class TestPaymentSuccess:
    """Test payment worker happy paths."""

    @pytest.fixture
    def worker(self) -> PaymentWorker:
        return PaymentWorker()

    @pytest.mark.asyncio
    async def test_process_payment_success(self, worker: PaymentWorker) -> None:
        """Should create payment and update order."""
        mock_order = {
            "id": 1,
            "order_number": "R-001",
            "amount": "1000.00",
            "loyalty_used": "100.00",
            "payment_status": "pending",
            "items_json": json.dumps([{"name": "Pizza", "price": 500, "quantity": 2}]),
            "user_email": "test@test.com",
            "phone": "+79990000000",
        }

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_order)
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_payment = MagicMock()
        mock_payment.id = "pay_123"
        mock_payment.confirmation.confirmation_url = "https://pay.url"
        mock_payment.status = "pending"

        with patch("payments.worker.get_raw_pool", return_value=mock_pool):
            with patch("payments.worker.Payment.create", return_value=mock_payment):
                result = await worker.process_payment("tenant_test", 1, "http://return")

        assert result["payment_id"] == "pay_123"  # nosec B101
        assert result["confirmation_url"] == "https://pay.url"  # nosec B101
