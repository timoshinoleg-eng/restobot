# tests/test_orders_integration.py
"""Integration-style tests for order endpoints with mocked DB."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestGetOrder:
    """Test GET /orders/{order_id}."""

    def test_get_order_not_found(self, client: TestClient) -> None:
        """Should return 404 when order not found."""
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value=None)

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/orders/999",
                headers={"X-Tenant-ID": "test"},
            )
        assert response.status_code == 404  # nosec B101
        assert response.json()["detail"] == "Order not found"  # nosec B101


class TestListOrders:
    """Test GET /orders."""

    def test_list_orders_empty(self, client: TestClient) -> None:
        """Should return empty list when no orders."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/orders",
                headers={"X-Tenant-ID": "test"},
            )
        assert response.status_code == 200  # nosec B101
        assert response.json() == []  # nosec B101
