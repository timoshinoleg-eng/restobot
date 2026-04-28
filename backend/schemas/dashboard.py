"""Dashboard schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RevenueSeriesQuery(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    group_by: str = Field(default="day", pattern=r"^(hour|day)$")


class TopDishOut(BaseModel):
    dish_id: int | None
    name: str
    qty: Decimal
    revenue: Decimal


class DashboardSummaryOut(BaseModel):
    revenue: Decimal
    orders_count: int
    avg_check: Decimal
    top_dishes: list[TopDishOut]
