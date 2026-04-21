# api/routes/orders.py
"""Order management endpoints."""

import logging
import secrets
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

PHONE_REGEX = r"^\+7\d{10}$"


class OrderItemRequest(BaseModel):
    menu_item_id: int = Field(..., ge=1)
    quantity: int = Field(default=1, ge=1, le=100)
    modifiers: Optional[list[dict[str, Any]]] = None
    price: float = Field(..., gt=0)


class OrderCreateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    type: str = Field(..., pattern=r"^(delivery|pickup|dine_in|pre_order)$")
    items: list[OrderItemRequest] = Field(..., min_length=1)
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, pattern=PHONE_REGEX)
    comment: Optional[str] = Field(default=None, max_length=1000)
    scheduled_for: Optional[str] = None
    payment_method: str = Field(default="cash", pattern=r"^(cash|card|online)$")
    loyalty_points_to_use: Optional[float] = Field(default=0.0, ge=0)

    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list[OrderItemRequest]) -> list[OrderItemRequest]:
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

    @field_validator("address")
    @classmethod
    def validate_address_for_delivery(cls, v: Optional[str], info: Any) -> Optional[str]:
        data = info.data
        if data.get("type") == "delivery" and not v:
            raise ValueError("Address is required for delivery orders")
        return v


class OrderItemResponse(BaseModel):
    menu_item_id: int
    quantity: int
    modifiers: Optional[list[dict[str, Any]]]
    price: float


class OrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    payment_status: str
    amount: float
    items: list[OrderItemResponse]
    created_at: str


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(request: Request, body: OrderCreateRequest) -> dict[str, Any]:
    """Create a new order with transactional safety."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    total = sum(item.price * item.quantity for item in body.items)

    # Generate order number using cryptographically secure random
    order_number = f"R-{datetime.now().strftime('%y%m%d')}-" f"{secrets.randbelow(9000) + 1000}"

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Validate minimum order amount
            settings_row = await conn.fetchrow(
                format_sql(
                    "SELECT min_order_amount FROM {}.restaurant_settings LIMIT 1",
                    tenant_schema,
                ),
            )
            if settings_row and total < float(settings_row["min_order_amount"]):
                raise HTTPException(
                    status_code=422,
                    detail=f"Minimum order amount: {settings_row['min_order_amount']} ₽",
                )

            # Apply loyalty points with row-level lock
            if body.loyalty_points_to_use and body.loyalty_points_to_use > 0:
                user = await conn.fetchrow(
                    format_sql(
                        """
                        SELECT loyalty_points
                        FROM {}.users
                        WHERE id = $1
                        FOR UPDATE
                        """,
                        tenant_schema,
                    ),
                    body.user_id,
                )
                if not user or float(user["loyalty_points"]) < body.loyalty_points_to_use:
                    raise HTTPException(status_code=422, detail="Insufficient loyalty points")
                if body.loyalty_points_to_use > total * 0.5:
                    raise HTTPException(
                        status_code=422,
                        detail="Max 50% discount with loyalty points",
                    )

            # Insert order
            order_id = await conn.fetchval(
                format_sql(
                    """
                    INSERT INTO {}.orders (
                        user_id, order_number, type, status, payment_status,
                        payment_method, amount, delivery_fee, discount_amount, loyalty_used,
                        items_json, address, phone, comment, scheduled_for
                    ) VALUES (
                        $1, $2, $3, 'new', 'pending', $4, $5, 0,
                        $6, $7, $8, $9, $10, $11, $12
                    )
                    RETURNING id
                    """,
                    tenant_schema,
                ),
                body.user_id,
                order_number,
                body.type,
                body.payment_method,
                total,
                body.loyalty_points_to_use,
                body.loyalty_points_to_use,
                [item.model_dump() for item in body.items],
                body.address,
                body.phone,
                body.comment,
                body.scheduled_for,
            )

            # Deduct loyalty points and log transaction atomically
            if body.loyalty_points_to_use and body.loyalty_points_to_use > 0:
                await conn.execute(
                    format_sql(
                        """
                        UPDATE {}.users
                        SET loyalty_points = loyalty_points - $1
                        WHERE id = $2
                        """,
                        tenant_schema,
                    ),
                    body.loyalty_points_to_use,
                    body.user_id,
                )
                await conn.execute(
                    format_sql(
                        """
                        INSERT INTO {}.loyalty_transactions
                        (user_id, order_id, type, points, balance_after, description)
                        VALUES (
                            $1, $2, 'spend', $3,
                            (SELECT loyalty_points FROM {}.users WHERE id = $1),
                            'Order #{4}'
                        )
                        """,
                        tenant_schema,
                        tenant_schema,
                    ),
                    body.user_id,
                    order_id,
                    -body.loyalty_points_to_use,
                    order_number,
                )

    return {
        "id": order_id,
        "order_number": order_number,
        "status": "new",
        "payment_status": "pending",
        "amount": float(total),
        "items": [item.model_dump() for item in body.items],
        "created_at": datetime.now().isoformat(),
    }


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(request: Request, order_id: int) -> dict[str, Any]:
    """Get order by ID."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.orders WHERE id = $1", tenant_schema),
        order_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    return dict(row)


@router.get("/orders")
async def list_orders(
    request: Request,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List orders with filters."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql("SELECT * FROM {}.orders WHERE 1=1", tenant_schema)
    params: list[Any] = []

    if user_id:
        params.append(user_id)
        query += f" AND user_id = ${len(params)}"

    if status:
        params.append(status)
        query += f" AND status = ${len(params)}"

    query += " ORDER BY created_at DESC LIMIT 50"

    rows = await pool.fetch(query, *params)
    return [dict(row) for row in rows]
