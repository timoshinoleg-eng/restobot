# shared/models.py
"""SQLAlchemy models for shared schema."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base


class Tenant(Base):  # type: ignore[misc]
    """Restaurant tenant (shared schema)."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "shared"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12))
    ogrn: Mapped[Optional[str]] = mapped_column(String(15))
    legal_address: Mapped[Optional[str]] = mapped_column(String(500))
    actual_address: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    status: Mapped[str] = mapped_column(String(20), default="active")
    dpo_name: Mapped[Optional[str]] = mapped_column(String(255))
    dpo_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="tenant")


class Plan(Base):  # type: ignore[misc]
    """Subscription plans."""

    __tablename__ = "plans"
    __table_args__ = {"schema": "shared"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    price_monthly: Mapped[Decimal] = mapped_column(nullable=False)
    max_menu_items: Mapped[int] = mapped_column(Integer, default=100)
    max_staff: Mapped[int] = mapped_column(Integer, default=10)
    max_orders_day: Mapped[int] = mapped_column(Integer, default=500)
    has_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    has_delivery: Mapped[bool] = mapped_column(Boolean, default=False)
    has_loyalty: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")


class Subscription(Base):  # type: ignore[misc]
    """Tenant subscriptions."""

    __tablename__ = "subscriptions"
    __table_args__ = {"schema": "shared"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("shared.tenants.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("shared.plans.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")
