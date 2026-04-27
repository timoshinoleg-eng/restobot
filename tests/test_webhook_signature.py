# tests/test_webhook_signature.py
"""Tests for YooKassa webhook signature verification."""

import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from shared.config import get_settings

settings = get_settings()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestWebhookSignature:
    """Verify webhook HMAC checks."""

    def test_valid_signature_accepted(self, client: TestClient) -> None:
        """Should accept webhook with valid HMAC signature."""
        body = b'{"event":"payment.succeeded","object":{"id":"pay_123"}}'
        secret = settings.YOOKASSA_WEBHOOK_SECRET or "test-secret"
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        with patch("shared.config.get_settings") as mock_settings:
            cfg = get_settings()
            mock_settings.return_value = cfg
            with patch("api.routes.payments.settings.YOOKASSA_WEBHOOK_SECRET", secret):
                with patch("payments.worker.PaymentWorker.handle_webhook", new_callable=AsyncMock):
                    response = client.post(
                        "/api/v1/test/webhook/yookassa",
                        headers={"X-Webhook-Signature": sig},
                        content=body,
                    )
        assert response.status_code == 200  # nosec B101

    def test_invalid_signature_rejected(self, client: TestClient) -> None:
        """Should reject webhook with bad signature."""
        body = b'{"event":"payment.succeeded"}'
        secret = "test-secret"

        with patch("api.routes.payments.settings.YOOKASSA_WEBHOOK_SECRET", secret):
            response = client.post(
                "/api/v1/test/webhook/yookassa",
                headers={"X-Webhook-Signature": "bad-sig"},
                content=body,
            )
        assert response.status_code == 400  # nosec B101
        assert response.json()["detail"] == "Invalid signature"  # nosec B101
