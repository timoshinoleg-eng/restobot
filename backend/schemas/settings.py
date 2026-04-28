"""Tenant settings schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    restaurant_display_name: str
    legal_name: str | None
    phone: str | None
    support_email: str | None
    bot_name: str
    greeting_text: str | None
    ai_enabled: bool
    web_widget_enabled: bool
    timezone: str
    currency: str
    min_order_amount: Decimal
    delivery_enabled: bool
    pickup_enabled: bool
    address_json: dict[str, object]
    working_hours_json: dict[str, object]


class SettingsUpdate(BaseModel):
    restaurant_display_name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    support_email: str | None = Field(default=None, max_length=255)
    bot_name: str | None = Field(default=None, min_length=1, max_length=255)
    greeting_text: str | None = Field(default=None, max_length=4000)
    ai_enabled: bool | None = None
    web_widget_enabled: bool | None = None
    timezone: str | None = Field(default=None, max_length=50)
    min_order_amount: Decimal | None = Field(default=None, ge=0)
    delivery_enabled: bool | None = None
    pickup_enabled: bool | None = None
    address_json: dict[str, object] | None = None
    working_hours_json: dict[str, object] | None = None
