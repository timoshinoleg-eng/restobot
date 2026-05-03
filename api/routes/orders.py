# api/routes/orders.py
"""Order management endpoints."""

import json
import logging
import re
import secrets
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from shared.audit_utils import log_audit
from shared.auth_dependencies import require_admin_user
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

    @field_validator("modifiers")
    @classmethod
    def validate_modifiers(
        cls, v: Optional[list[dict[str, Any]]]
    ) -> Optional[list[dict[str, Any]]]:
        if v:
            for mod in v:
                if "modifier_option_id" not in mod:
                    raise ValueError("Modifier missing modifier_option_id")
        return v


class OrderCreateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    type: str = Field(..., pattern=r"^(delivery|pickup|dine_in|pre_order)$")
    items: list[OrderItemRequest] = Field(..., min_length=1)
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=20)
    comment: Optional[str] = Field(default=None, max_length=1000)
    scheduled_for: Optional[str] = None
    payment_method: str = Field(default="cash", pattern=r"^(cash|card|online)$")
    loyalty_points_to_use: float = Field(default=0.0, ge=0)

    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list[OrderItemRequest]) -> list[OrderItemRequest]:
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = "".join(ch for ch in v if ch.isdigit())
        if len(digits) == 11 and digits.startswith("8"):
            normalized = "+7" + digits[1:]
        elif len(digits) == 10:
            normalized = "+7" + digits
        elif len(digits) == 11 and digits.startswith("7"):
            normalized = "+" + digits
        else:
            normalized = v
        if not re.match(PHONE_REGEX, normalized):
            raise ValueError("Invalid phone format")
        return normalized

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


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(new|confirmed|preparing|ready|delivering|completed|cancelled)$")
    payment_status: Optional[str] = Field(default=None, pattern=r"^(pending|paid|failed|refunded)$")


async def _reserve_ingredients(
    conn: Any, tenant_schema: str, items: list[OrderItemRequest]
) -> None:
    """Reserve ingredients for order items; raise 422 if insufficient stock."""
    for item in items:
        recipe = await conn.fetch(
            format_sql(
                "SELECT ingredient_id, grams_needed FROM {}.recipes WHERE menu_item_id = $1",
                tenant_schema,
            ),
            item.menu_item_id,
        )
        if not recipe:
            continue
        for ing in recipe:
            needed = float(ing["grams_needed"]) * item.quantity
            stock = await conn.fetchrow(
                format_sql(
                    "SELECT current_stock as available FROM {}.ingredients WHERE id = $1",
                    tenant_schema,
                ),
                ing["ingredient_id"],
            )
            if not stock or float(stock["available"]) < needed:
                raise HTTPException(status_code=422, detail="Insufficient stock")
            await conn.fetchrow(
                format_sql(
                    """
                    UPDATE {}.ingredients
                    SET current_stock = current_stock - $1
                    WHERE id = $2
                    RETURNING current_stock
                    """,
                    tenant_schema,
                ),
                needed,
                ing["ingredient_id"],
            )


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(request: Request, body: OrderCreateRequest) -> Any:
    """Create a new order with transactional safety."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    total = sum(item.price * item.quantity for item in body.items)

    # Generate order number using cryptographically secure random
    order_number = f"R-{datetime.now().strftime('%y%m%d')}-" f"{secrets.randbelow(9000) + 1000}"

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Idempotency check
            idempotency_key = request.headers.get("Idempotency-Key")
            if idempotency_key:
                existing = await conn.fetchrow(
                    format_sql(
                        "SELECT * FROM {}.orders WHERE idempotency_key = $1",
                        tenant_schema,
                    ),
                    idempotency_key,
                )
                if existing:
                    items_json = existing["items_json"]
                    if isinstance(items_json, str):
                        items_json = json.loads(items_json)
                    for it in items_json:
                        if "modifiers" not in it:
                            it["modifiers"] = None
                    created_at = existing["created_at"]
                    if hasattr(created_at, "isoformat"):
                        created_at = created_at.isoformat()
                    else:
                        created_at = str(created_at)
                    return Response(
                        status_code=200,
                        content=__import__("json").dumps({
                            "id": existing["id"],
                            "order_number": existing["order_number"],
                            "status": existing["status"],
                            "payment_status": existing["payment_status"],
                            "amount": float(existing["amount"]),
                            "items": items_json,
                            "created_at": created_at,
                        }),
                        media_type="application/json",
                    )

            # Validate prices and modifiers
            for item in body.items:
                menu_item = await conn.fetchrow(
                    format_sql(
                        "SELECT price FROM {}.menu_items WHERE id = $1",
                        tenant_schema,
                    ),
                    item.menu_item_id,
                )
                if not menu_item:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Menu item {item.menu_item_id} not found",
                    )
                expected_price = float(menu_item["price"])
                if item.modifiers:
                    for mod in item.modifiers:
                        option = await conn.fetchrow(
                            format_sql(
                                "SELECT price FROM {}.modifier_options WHERE id = $1",
                                tenant_schema,
                            ),
                            mod["modifier_option_id"],
                        )
                        if option:
                            expected_price += float(option["price"])
                if abs(expected_price - item.price) > 0.01:
                    raise HTTPException(status_code=422, detail="Price mismatch")

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

            # Reserve ingredients / check stock
            await _reserve_ingredients(conn, tenant_schema, body.items)

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
                json.dumps([item.model_dump() for item in body.items]),
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
                            $4
                        )
                        """,
                        tenant_schema,
                        tenant_schema,
                    ),
                    body.user_id,
                    order_id,
                    -body.loyalty_points_to_use,
                    f"Order #{order_number}",
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
    order_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
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

    if order_type:
        params.append(order_type)
        query += f" AND type = ${len(params)}"

    if date_from:
        params.append(date_from)
        query += f" AND created_at >= ${len(params)}"

    if date_to:
        params.append(date_to)
        query += f" AND created_at <= ${len(params)}"

    params.append(limit)
    query += f" ORDER BY created_at DESC LIMIT ${len(params)}"

    params.append(offset)
    query += f" OFFSET ${len(params)}"

    rows = await pool.fetch(query, *params)
    return [dict(row) for row in rows]


@router.put("/orders/{order_id}/status")
async def update_order_status_route(
    request: Request, order_id: int, body: OrderStatusUpdateRequest
) -> dict[str, Any]:
    """Update order status. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.orders WHERE id = $1", tenant_schema),
        order_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Order not found")

    row = await pool.fetchrow(
        format_sql(
            """
            UPDATE {}.orders
            SET status = $1,
                payment_status = COALESCE($2, payment_status),
                updated_at = NOW()
            WHERE id = $3
            RETURNING id, order_number, status, payment_status, amount, created_at
            """,
            tenant_schema,
        ),
        body.status,
        body.payment_status,
        order_id,
    )
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE_STATUS",
        table_name="orders",
        record_id=order_id,
        old_values={"status": old_row["status"], "payment_status": old_row["payment_status"]},
        new_values={"status": row["status"], "payment_status": row["payment_status"]},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "id": int(row["id"]),
        "order_number": row["order_number"],
        "status": row["status"],
        "payment_status": row["payment_status"],
        "amount": float(row["amount"]),
    }
