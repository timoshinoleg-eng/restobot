"""Tests verifying YooKassa endpoints are blocked when disabled."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app as legacy_app
from apps.public_api.main import app as public_app
from payments.worker import PaymentWorker


class TestPaymentsDisabled:
    """Ensure online payment paths are fail-closed when YOOKASSA_ENABLED=false."""

    @pytest.fixture
    def public_client(self) -> TestClient:
        return TestClient(public_app)

    @pytest.fixture
    def legacy_client(self) -> TestClient:
        return TestClient(legacy_app)

    def test_create_payment_returns_503_when_disabled(self, public_client: TestClient) -> None:
        """POST /orders/{id}/payment must return 503 when YooKassa is off."""
        headers = {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwidXNlcl9pZCI6MSwidGVuYW50X2lkIjoidGVzdCIsInJvbGUiOiJ1c2VyIiwiZXhwIjo5OTk5OTk5OTl9.fake"}
        response = public_client.post("/api/v1/test/orders/1/payment", headers=headers)
        assert response.status_code == 503  # nosec B101
        assert "disabled" in response.json()["detail"].lower()  # nosec B101

    def test_webhook_returns_503_when_disabled(self, legacy_client: TestClient) -> None:
        """POST /webhook/yookassa must return 503 when YooKassa is off."""
        response = legacy_client.post("/api/v1/test/webhook/yookassa")
        assert response.status_code == 503  # nosec B101

    @pytest.mark.asyncio
    async def test_process_payment_raises_when_disabled(self) -> None:
        """Worker.process_payment must raise RuntimeError when disabled."""
        worker = PaymentWorker()
        with pytest.raises(RuntimeError, match="disabled"):
            await worker.process_payment("tenant_test", 1, "http://return")

    @pytest.mark.asyncio
    async def test_handle_webhook_warns_when_disabled(self) -> None:
        """Worker.handle_webhook must log and return early when disabled."""
        worker = PaymentWorker()
        with patch("payments.worker.logger") as mock_logger:
            await worker.handle_webhook(
                "tenant_test",
                {"object": {"id": "pay_123"}, "event": "payment.succeeded"},
            )
        mock_logger.warning.assert_called_once()
