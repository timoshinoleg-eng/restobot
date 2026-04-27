# tests/test_modifiers.py
"""Tests for dish modifier price calculations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.orders import OrderItemRequest
from tests.conftest import get_test_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestModifierValidation:
    """Test modifier option validation."""

    def test_order_item_with_modifier_option_id(self) -> None:
        """Modifier dict must contain modifier_option_id."""
        item = OrderItemRequest(
            menu_item_id=1, quantity=1, price=500, modifiers=[{"modifier_option_id": 2}]
        )
        assert item.modifiers is not None  # nosec B101
        assert item.modifiers[0]["modifier_option_id"] == 2  # nosec B101

    def test_missing_modifier_option_id_raises(self) -> None:
        """Modifier without modifier_option_id should fail validation."""
        with pytest.raises(Exception):
            OrderItemRequest(
                menu_item_id=1, quantity=1, price=500, modifiers=[{"name": "extra cheese"}]
            )

    def test_price_mismatch_rejected(self, client: TestClient) -> None:
        """Server should reject order when provided price doesn't match calculated."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        # No idempotency header -> skip idempotency check
        # Calls: menu item price, modifier option price, settings
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"price": 400},  # menu item
            {"price": 150},  # modifier option
            {"min_order_amount": 0},  # settings
        ])
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.orders.get_raw_pool", return_value=mock_pool):
            with patch("api.routes.orders._reserve_ingredients", new_callable=AsyncMock):
                response = client.post(
                    "/api/v1/test/orders",
                    headers={
                        "X-Tenant-ID": "test",
                        "Authorization": f"Bearer {get_test_token()}",
                    },
                    json={
                        "user_id": 1,
                        "type": "pickup",
                        "items": [
                            {
                                "menu_item_id": 1,
                                "quantity": 1,
                                "price": 500,
                                "modifiers": [{"modifier_option_id": 2}],
                            }
                        ],
                        "phone": "+79990000000",
                    },
                )
        assert response.status_code == 422  # nosec B101
        assert "Price mismatch" in response.json()["detail"]  # nosec B101
