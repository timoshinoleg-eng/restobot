"""Order domain services."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.audit.service import write_audit_log
from backend.menu.models import MenuItem
from backend.orders.models import GuestSession, Order, OrderEvent, OrderItem
from backend.schemas.orders import ManualOrderCreate, OrderOut
from backend.schemas.widget import WidgetOrderCreate
from shared.config import get_settings
from shared.redis_client import get_redis

settings = get_settings()

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"accepted", "cancelled"},
    "accepted": {"preparing", "cancelled"},
    "preparing": {"ready"},
    "ready": {"delivering", "completed"},
    "delivering": {"completed"},
}


def _order_number() -> str:
    return f"R-{datetime.now(timezone.utc).strftime('%y%m%d')}-{secrets.randbelow(9000) + 1000}"


def create_guest_session_token(*, session_id: UUID, tenant_id: str) -> str:
    payload = {
        "sid": str(session_id),
        "tenant_id": tenant_id,
        "type": "guest_session",
        "exp": int(datetime.now(timezone.utc).timestamp()) + settings.REDIS_CART_TTL,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_guest_session_token(token: str) -> dict[str, str] | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "guest_session":
            return None
        return {"session_id": payload["sid"], "tenant_id": payload["tenant_id"]}
    except JWTError:
        return None


async def publish_order_event(tenant_id: str, event: dict[str, object]) -> None:
    redis = await get_redis()
    await redis.publish(f"tenant:{tenant_id}:orders", json.dumps(event, default=str))


async def create_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    source_channel: str,
    actor_user_id: int | None,
    actor_role: str | None,
    actor_ip: str | None,
    customer_name: str | None,
    phone: str | None,
    order_type: str,
    address: str | None,
    comment: str | None,
    payment_method: str,
    items: list[dict[str, object]],
    guest_session_id: UUID | None = None,
    status: str = "new",
) -> Order:
    menu_item_ids = [int(item["menu_item_id"]) for item in items]
    rows = await db.execute(select(MenuItem).where(MenuItem.id.in_(menu_item_ids), MenuItem.is_available.is_(True)))
    menu_items = {item.id: item for item in rows.scalars().all()}
    if len(menu_items) != len(menu_item_ids):
        raise ValueError("One or more menu items are unavailable")

    order_items_payload: list[dict[str, object]] = []
    subtotal = Decimal("0")
    normalized_items: list[OrderItem] = []
    for payload in items:
        menu_item_id = int(payload["menu_item_id"])
        quantity = Decimal(str(payload["quantity"]))
        menu_item = menu_items[menu_item_id]
        line_total = menu_item.price * quantity
        subtotal += line_total
        modifiers_json = payload.get("modifier_option_ids") or payload.get("modifiers_json") or []
        order_items_payload.append(
            {
                "menu_item_id": menu_item_id,
                "name": menu_item.name,
                "quantity": float(quantity),
                "price": float(menu_item.price),
                "modifiers": modifiers_json,
            }
        )
        normalized_items.append(
            OrderItem(
                menu_item_id=menu_item_id,
                item_name_snapshot=menu_item.name,
                sku_snapshot=menu_item.sku,
                unit_price=menu_item.price,
                quantity=quantity,
                line_total=line_total,
                modifiers_json=list(modifiers_json) if isinstance(modifiers_json, list) else [],
            )
        )

    order = Order(
        user_id=actor_user_id,
        guest_session_id=guest_session_id,
        source_channel=source_channel,
        order_number=_order_number(),
        type=order_type,
        status=status,
        payment_status="pending",
        payment_method=payment_method,
        customer_name=customer_name,
        phone=phone,
        address=address,
        comment=comment,
        amount=subtotal,
        subtotal=subtotal,
        discount_amount=Decimal("0"),
        delivery_fee=Decimal("0"),
        total_amount=subtotal,
        loyalty_used=Decimal("0"),
        items_json=order_items_payload,
    )
    db.add(order)
    await db.flush()

    for item in normalized_items:
        item.order_id = order.id
        db.add(item)

    db.add(
        OrderEvent(
            order_id=order.id,
            event_type="created",
            from_status=None,
            to_status=status,
            actor_type="employee" if actor_user_id else "guest",
            actor_id=actor_user_id,
            payload={"source_channel": source_channel},
        )
    )
    await write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_ip=actor_ip,
        entity_type="order",
        entity_id=str(order.id),
        action="create",
        new_value={"status": status, "source_channel": source_channel, "total_amount": str(subtotal)},
    )
    await db.flush()
    order_with_rel = await get_order_by_id(db, order.id)
    if order_with_rel is None:
        raise ValueError("Failed to load created order")
    await publish_order_event(
        tenant_id,
        {
            "event": "new_order",
            "tenant_id": tenant_id,
            "entity": "order",
            "entity_id": order.id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "order_number": order.order_number,
                "status": order.status,
                "amount": float(subtotal),
                "source_channel": source_channel,
            },
        },
    )
    return order_with_rel


async def get_order_by_id(db: AsyncSession, order_id: int) -> Order | None:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.events))
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def update_order_status(
    db: AsyncSession,
    *,
    tenant_id: str,
    order: Order,
    new_status: str,
    actor_user_id: int | None,
    actor_role: str | None,
    actor_ip: str | None,
    comment: str | None,
) -> Order:
    allowed = ALLOWED_STATUS_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise ValueError(f"Transition {order.status} -> {new_status} is not allowed")

    previous_status = order.status
    order.status = new_status
    if new_status == "completed":
        order.closed_at = datetime.now(timezone.utc)
    db.add(
        OrderEvent(
            order_id=order.id,
            event_type="status_changed",
            from_status=previous_status,
            to_status=new_status,
            actor_type="employee",
            actor_id=actor_user_id,
            payload={"comment": comment} if comment else {},
        )
    )
    await write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_ip=actor_ip,
        entity_type="order",
        entity_id=str(order.id),
        action="update",
        old_value={"status": previous_status},
        new_value={"status": new_status},
        reason=comment,
    )
    await db.flush()
    await publish_order_event(
        tenant_id,
        {
            "event": "order_status_changed",
            "tenant_id": tenant_id,
            "entity": "order",
            "entity_id": order.id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"from_status": previous_status, "to_status": new_status},
        },
    )
    refreshed = await get_order_by_id(db, order.id)
    if refreshed is None:
        raise ValueError("Updated order not found")
    return refreshed


def order_to_schema(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        source_channel=order.source_channel,
        customer_name=order.customer_name,
        phone=order.phone,
        total_amount=order.total_amount,
        created_at=order.created_at,
        items=[
            {
                "id": item.id,
                "menu_item_id": item.menu_item_id,
                "item_name_snapshot": item.item_name_snapshot,
                "sku_snapshot": item.sku_snapshot,
                "unit_price": item.unit_price,
                "quantity": item.quantity,
                "line_total": item.line_total,
                "modifiers_json": item.modifiers_json,
            }
            for item in getattr(order, "items", [])
        ],
        events=[
            {
                "id": event.id,
                "event_type": event.event_type,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "actor_type": event.actor_type,
                "actor_id": event.actor_id,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            for event in getattr(order, "events", [])
        ],
    )
