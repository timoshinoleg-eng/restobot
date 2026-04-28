"""Tenant-scoped settings models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class TenantSettings(Base):  # type: ignore[misc]
    """Tenant settings used by admin panel and public channels."""

    __tablename__ = "tenant_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    restaurant_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    support_email: Mapped[str | None] = mapped_column(String(255))
    bot_name: Mapped[str] = mapped_column(String(255), default="RestoBot", nullable=False)
    greeting_text: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    web_widget_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    address_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    working_hours_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    yookassa_shop_id: Mapped[str | None] = mapped_column(String(128))
    yookassa_secret_ref: Mapped[str | None] = mapped_column(String(255))
    telegram_bot_token_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
