"""Order management endpoints for admin API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.admin_api.dependencies import require_active_subscription
from apps.admin_api.middleware import get_db
from backend.auth.permissions import require_permission
from backend.orders.models import Order
from backend.orders.service import create_order, get_order_by_id, order_to_schema, update_order_status
from backend.schemas.orders import ManualOrderCreate, OrderListOut, OrderOut, OrderStatusUpdate

router = APIRouter(prefix="/admin/v1/orders", tags=["orders"])


@router.get("", response_model=OrderListOut, dependencies=[Depends(require_permission("orders.read"))])
async def list_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    source_channel: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> OrderListOut:
    query = select(Order).options(selectinload(Order.items), selectinload(Order.events))
    count_query = select(func.count()).select_from(Order)
    filters = []
    if status_filter:
        filters.append(Order.status == status_filter)
    if source_channel:
        filters.append(Order.source_channel == source_channel)
    if date_from:
        filters.append(Order.created_at >= date_from)
    if date_to:
        filters.append(Order.created_at <= date_to)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Order.order_number.ilike(pattern),
                Order.customer_name.ilike(pattern),
                Order.phone.ilike(pattern),
            )
        )
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())
    rows = await db.execute(
        query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = [order_to_schema(order) for order in rows.scalars().all()]
    return OrderListOut(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    dependencies=[Depends(require_permission("orders.read"))],
)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)) -> OrderOut:
    order = await get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order_to_schema(order)


@router.patch(
    "/{order_id}/status",
    response_model=OrderOut,
    dependencies=[Depends(require_active_subscription)],
)
async def patch_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    current_role = getattr(request.state, "user_role", "")
    if body.status in {"preparing", "ready"} and order.status in {"accepted", "preparing"}:
        require_permission("orders.status.kitchen")(request)
    else:
        require_permission("orders.write")(request)

    try:
        updated = await update_order_status(
            db,
            tenant_id=request.state.tenant_id,
            order=order,
            new_status=body.status,
            actor_user_id=getattr(request.state, "user_id", None),
            actor_role=current_role,
            actor_ip=request.client.host if request.client else None,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return order_to_schema(updated)


@router.post(
    "/manual",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("orders.write")), Depends(require_active_subscription)],
)
async def create_manual_order(
    body: ManualOrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await create_order(
        db,
        tenant_id=request.state.tenant_id,
        source_channel="admin",
        actor_user_id=getattr(request.state, "user_id", None),
        actor_role=getattr(request.state, "user_role", None),
        actor_ip=request.client.host if request.client else None,
        customer_name=body.customer_name,
        phone=body.phone,
        order_type=body.order_type,
        address=body.address,
        comment=body.comment,
        payment_method=body.payment_method,
        items=[item.model_dump() for item in body.items],
        status="accepted",
    )
    return order_to_schema(order)
