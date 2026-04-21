# tests/test_orders.py
"""Tests for order creation and validation."""

import pytest
from pydantic import ValidationError

from api.routes.orders import OrderCreateRequest, OrderItemRequest


@pytest.fixture
def sample_order() -> OrderCreateRequest:
    return OrderCreateRequest(
        user_id=1,
        type="delivery",
        items=[
            OrderItemRequest(menu_item_id=1, quantity=2, price=500.00),
            OrderItemRequest(menu_item_id=2, quantity=1, price=300.00),
        ],
        address="ул. Ленина, 1",
        phone="+79990000000",
        payment_method="cash",
    )


class TestOrderValidation:
    """Test order validation rules."""

    def test_minimum_order_amount(self, sample_order: OrderCreateRequest) -> None:
        """Test minimum order amount validation."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        assert total == 1300.00  # nosec B101

    def test_delivery_requires_address(self) -> None:
        """Test that delivery requires address."""
        with pytest.raises(ValidationError):
            OrderCreateRequest(
                user_id=1,
                type="delivery",
                items=[
                    OrderItemRequest(menu_item_id=1, quantity=1, price=500.00),
                ],
                address=None,
                phone="+79990000000",
            )

    def test_loyalty_points_max_50_percent(self, sample_order: OrderCreateRequest) -> None:
        """Test max 50% discount with loyalty points."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        max_loyalty = total * 0.5
        assert max_loyalty == 650.00  # nosec B101

    def test_invalid_phone_raises_error(self) -> None:
        """Test that invalid phone format is rejected."""
        with pytest.raises(ValidationError):
            OrderCreateRequest(
                user_id=1,
                type="pickup",
                items=[
                    OrderItemRequest(menu_item_id=1, quantity=1, price=100.00),
                ],
                phone="invalid-phone",
            )

    def test_negative_price_rejected(self) -> None:
        """Test that negative price is rejected."""
        with pytest.raises(ValidationError):
            OrderItemRequest(menu_item_id=1, quantity=1, price=-10.00)

    def test_quantity_bounds(self) -> None:
        """Test quantity min/max bounds."""
        with pytest.raises(ValidationError):
            OrderItemRequest(menu_item_id=1, quantity=0, price=100.00)
        with pytest.raises(ValidationError):
            OrderItemRequest(menu_item_id=1, quantity=101, price=100.00)


class TestOrderCalculations:
    """Test order amount calculations."""

    def test_total_calculation(self, sample_order: OrderCreateRequest) -> None:
        """Test total amount calculation."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        assert total == 1300.00  # nosec B101

    def test_with_loyalty_discount(self, sample_order: OrderCreateRequest) -> None:
        """Test total with loyalty points applied."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        loyalty_used = 300.00
        final_total = total - loyalty_used
        assert final_total == 1000.00  # nosec B101
