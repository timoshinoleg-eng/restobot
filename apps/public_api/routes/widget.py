"""Widget guest API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.public_api.middleware import get_public_db
from backend.menu.models import MenuCategory, MenuItem
from backend.orders.models import GuestSession
from backend.orders.service import create_guest_session_token, create_order, order_to_schema
from backend.schemas.menu import CategoryOut, DishOut
from backend.schemas.orders import OrderOut
from backend.schemas.widget import WidgetOrderCreate, WidgetSessionCreate, WidgetSessionOut
from shared.config import get_settings
from shared.database import AsyncSessionLocal
from shared.models import Tenant

router = APIRouter(prefix="/public/v1/widget", tags=["widget"])
settings = get_settings()


@router.post("/session", response_model=WidgetSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: WidgetSessionCreate) -> WidgetSessionOut:
    session = AsyncSessionLocal()
    try:
        tenant = await session.scalar(select(Tenant).where(Tenant.slug == body.tenant_slug, Tenant.deleted_at.is_(None)))
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant_key = str(tenant.id)
        tenant_schema = settings.get_tenant_schema(tenant_key)
        await session.begin()
        await session.execute(text(f"SET LOCAL search_path TO {tenant_schema}, shared"))
        guest_session = GuestSession(
            id=uuid4(),
            source_channel="web_widget",
            source_url=body.source_url,
            consent_personal_data=body.consent_personal_data,
            consent_marketing=body.consent_marketing,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.REDIS_CART_TTL),
        )
        session.add(guest_session)
        await session.commit()
        token = create_guest_session_token(session_id=guest_session.id, tenant_id=tenant_key)
        return WidgetSessionOut(
            session_id=guest_session.id,
            session_token=token,
            expires_at=guest_session.expires_at,
            tenant_slug=tenant.slug or tenant_key,
        )
    finally:
        await session.close()


@router.get("/menu")
async def get_menu(
    request: Request,
    db: AsyncSession = Depends(get_public_db),
    category: int | None = None,
) -> dict[str, object]:
    category_query = select(MenuCategory).where(MenuCategory.is_active.is_(True)).order_by(MenuCategory.sort_order)
    item_query = select(MenuItem).where(MenuItem.is_available.is_(True), MenuItem.is_deleted.is_(False)).order_by(MenuItem.sort_order)
    if category:
        item_query = item_query.where(MenuItem.category_id == category)
    categories = [CategoryOut.model_validate(item) for item in (await db.execute(category_query)).scalars().all()]
    items = [DishOut.model_validate(item) for item in (await db.execute(item_query)).scalars().all()]
    return {"categories": categories, "items": items}


@router.get("/menu/{dish_id}", response_model=DishOut)
async def get_dish(dish_id: int, db: AsyncSession = Depends(get_public_db)) -> DishOut:
    dish = await db.scalar(
        select(MenuItem).where(MenuItem.id == dish_id, MenuItem.is_available.is_(True), MenuItem.is_deleted.is_(False))
    )
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return DishOut.model_validate(dish)


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_widget_order(
    body: WidgetOrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_public_db),
) -> OrderOut:
    order = await create_order(
        db,
        tenant_id=request.state.tenant_id,
        source_channel="web_widget",
        actor_user_id=None,
        actor_role=None,
        actor_ip=request.client.host if request.client else None,
        customer_name=body.customer_name,
        phone=body.phone,
        order_type=body.order_type,
        address=body.address,
        comment=body.comment,
        payment_method=body.payment_method,
        items=[item.model_dump() for item in body.items],
        guest_session_id=request.state.guest_session_id,
        status="new",
    )
    return order_to_schema(order)
