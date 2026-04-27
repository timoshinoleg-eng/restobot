# tests/test_idempotency.py
"""Tests for order idempotency."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import get_test_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestOrderIdempotency:
    """Verify idempotency key deduplication."""

    def test_duplicate_idempotency_key_returns_existing(self, client: TestClient) -> None:
        """Second request with same key should return existing order."""
        existing = {
            "id": 42,
            "order_number": "R-240101-1234",
            "status": "new",
            "payment_status": "pending",
            "amount": 1000.0,
            "items_json": '[{"menu_item_id":1,"quantity":1,"price":500}]',
            "created_at": datetime.now(),
        }
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=existing)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            response = client.post(
                "/api/v1/test/orders",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token()}",
                    "Idempotency-Key": "key-123",
                },
                json={
                    "user_id": 1,
                    "type": "pickup",
                    "items": [{"menu_item_id": 1, "quantity": 1, "price": 500}],
                    "phone": "+79990000000",
                },
            )
        assert response.status_code == 200  # nosec B101
        assert response.json()["id"] == 42  # nosec B101

    def test_new_idempotency_key_creates_order(self, client: TestClient) -> None:
        """Unique key should proceed to creation."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[None, {"price": 500}, {"min_order_amount": 0}])
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=99)
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            with patch("api.routes.orders._reserve_ingredients", new_callable=AsyncMock):
                response = client.post(
                    "/api/v1/test/orders",
                    headers={
                        "X-Tenant-ID": "test",
                        "Authorization": f"Bearer {get_test_token()}",
                        "Idempotency-Key": "key-456",
                    },
                    json={
                        "user_id": 1,
                        "type": "pickup",
                        "items": [{"menu_item_id": 1, "quantity": 1, "price": 500}],
                        "phone": "+79990000000",
                    },
                )
        assert response.status_code == 201  # nosec B101
        assert response.json()["id"] == 99  # nosec B101
