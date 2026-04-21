# tests/test_models.py
"""Tests for SQLAlchemy models."""

from shared.database import Base
from shared.models import Plan, Subscription, Tenant


class TestModels:
    """Test model definitions."""

    def test_tenant_table_name(self) -> None:
        """Tenant model should have correct table name."""
        assert Tenant.__tablename__ == "tenants"  # nosec B101

    def test_plan_table_name(self) -> None:
        """Plan model should have correct table name."""
        assert Plan.__tablename__ == "plans"  # nosec B101

    def test_subscription_table_name(self) -> None:
        """Subscription model should have correct table name."""
        assert Subscription.__tablename__ == "subscriptions"  # nosec B101

    def test_models_registered_with_base(self) -> None:
        """All models should be registered with declarative base."""
        mappers = list(Base.registry.mappers)
        mapper_classes = [m.class_ for m in mappers]
        assert Tenant in mapper_classes  # nosec B101
        assert Plan in mapper_classes  # nosec B101
        assert Subscription in mapper_classes  # nosec B101
