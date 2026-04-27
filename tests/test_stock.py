# tests/test_stock.py
"""Tests for ingredient stock reservation during order creation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import get_test_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestStockReservation:
    """Verify stock locking and reservation."""

    def test_insufficient_stock_rejects_order(self, client: TestClient) -> None:
        """Should return 422 when ingredient stock is insufficient."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        # No idempotency header
        # Sequence: menu price, settings, recipe fetch, stock check
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"price": 500},  # menu item price
            {"min_order_amount": 0},  # settings
            {"available": 100},  # stock check (not enough for 2*200=400g)
        ])
        mock_conn.fetch = AsyncMock(return_value=[
            {"ingredient_id": 1, "grams_needed": 200}
        ])
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            response = client.post(
                "/api/v1/test/orders",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token()}",
                },
                json={
                    "user_id": 1,
                    "type": "pickup",
                    "items": [{"menu_item_id": 1, "quantity": 2, "price": 500}],
                    "phone": "+79990000000",
                },
            )
        assert response.status_code == 422  # nosec B101
        assert "Insufficient stock" in response.json()["detail"]  # nosec B101

    def test_sufficient_stock_accepts_order(self, client: TestClient) -> None:
        """Should create order when stock is sufficient."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"price": 500},  # menu item price
            {"min_order_amount": 0},  # settings
            {"available": 500},  # stock check (enough)
            {"current_stock": 300},  # after update
        ])
        mock_conn.fetch = AsyncMock(return_value=[
            {"ingredient_id": 1, "grams_needed": 200}
        ])
        mock_conn.fetchval = AsyncMock(return_value=77)
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            response = client.post(
                "/api/v1/test/orders",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token()}",
                },
                json={
                    "user_id": 1,
                    "type": "pickup",
                    "items": [{"menu_item_id": 1, "quantity": 1, "price": 500}],
                    "phone": "+79990000000",
                },
            )
        assert response.status_code == 201  # nosec B101
        assert response.json()["id"] == 77  # nosec B101
