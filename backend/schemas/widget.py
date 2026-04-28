"""Widget/guest-facing schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class WidgetSessionCreate(BaseModel):
    tenant_slug: str = Field(..., min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=1024)
    consent_personal_data: bool
    consent_marketing: bool = False


class WidgetSessionOut(BaseModel):
    session_id: UUID
    session_token: str
    expires_at: datetime
    tenant_slug: str


class WidgetOrderItemIn(BaseModel):
    menu_item_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    modifier_option_ids: list[int] = Field(default_factory=list)


class WidgetOrderCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    order_type: str = Field(..., pattern=r"^(delivery|pickup|dine_in|pre_order)$")
    address: str | None = Field(default=None, max_length=500)
    comment: str | None = Field(default=None, max_length=1000)
    payment_method: str = Field(default="cash", pattern=r"^(cash|card|online)$")
    items: list[WidgetOrderItemIn] = Field(..., min_length=1)
