"""Order admin schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: int | None
    item_name_snapshot: str
    sku_snapshot: str | None
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal
    modifiers_json: list[dict[str, object]]


class OrderEventOut(BaseModel):
    id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    actor_type: str
    actor_id: int | None
    payload: dict[str, object]
    created_at: datetime


class OrderOut(BaseModel):
    id: int
    order_number: str
    status: str
    payment_status: str
    source_channel: str | None
    customer_name: str | None
    phone: str | None
    total_amount: Decimal | None
    created_at: datetime
    items: list[OrderItemOut] = Field(default_factory=list)
    events: list[OrderEventOut] = Field(default_factory=list)


class OrderListOut(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    comment: str | None = Field(default=None, max_length=1000)


class ManualOrderItemCreate(BaseModel):
    menu_item_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)


class ManualOrderCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    order_type: str = Field(..., pattern=r"^(delivery|pickup|dine_in|pre_order)$")
    address: str | None = Field(default=None, max_length=500)
    comment: str | None = Field(default=None, max_length=1000)
    payment_method: str = Field(default="cash", pattern=r"^(cash|card|online)$")
    items: list[ManualOrderItemCreate] = Field(..., min_length=1)
