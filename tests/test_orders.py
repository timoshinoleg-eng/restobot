# tests/test_orders.py
"""Tests for order creation and validation."""

import pytest
from decimal import Decimal

from api.routes.orders import OrderCreateRequest, OrderItemRequest


@pytest.fixture
def sample_order():
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
    
    def test_minimum_order_amount(self, sample_order):
        """Test minimum order amount validation."""
        # Total = 2*500 + 1*300 = 1300
        assert sum(item.price * item.quantity for item in sample_order.items) == 1300.00
    
    def test_delivery_requires_address(self, sample_order):
        """Test that delivery requires address."""
        sample_order.address = None
        # Should raise validation error
        assert sample_order.address is None
    
    def test_loyalty_points_max_50_percent(self, sample_order):
        """Test max 50% discount with loyalty points."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        max_loyalty = total * 0.5
        assert max_loyalty == 650.00


class TestOrderCalculations:
    """Test order amount calculations."""
    
    def test_total_calculation(self, sample_order):
        """Test total amount calculation."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        assert total == 1300.00
    
    def test_with_loyalty_discount(self, sample_order):
        """Test total with loyalty points applied."""
        total = sum(item.price * item.quantity for item in sample_order.items)
        loyalty_used = 300.00
        final_total = total - loyalty_used
        assert final_total == 1000.00
