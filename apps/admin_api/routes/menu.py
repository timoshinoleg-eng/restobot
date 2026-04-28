"""Menu management endpoints for the admin API."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.dependencies import require_active_subscription
from apps.admin_api.middleware import get_db
from backend.audit.service import write_audit_log
from backend.auth.permissions import require_permission
from backend.menu.models import MenuCategory, MenuItem
from backend.schemas.menu import DishOut
from shared.storage import object_storage

router = APIRouter(prefix="/admin/v1/menu", tags=["menu"])


def _slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9а-яё]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-") or uuid.uuid4().hex


@router.post(
    "/dishes",
    response_model=DishOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("menu.write")), Depends(require_active_subscription)],
)
async def create_dish(
    request: Request,
    category_id: int = Form(..., ge=1),
    name: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(default=None, max_length=4000),
    price: Decimal = Form(...),
    old_price: Decimal | None = Form(default=None),
    weight_grams: int | None = Form(default=None),
    calories: int | None = Form(default=None),
    sku: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    allergens: str | None = Form(default=None),
    is_available: bool = Form(default=True),
    is_popular: bool = Form(default=False),
    sort_order: int = Form(default=100),
    photo: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> DishOut:
    """Create a tenant-scoped dish and persist an audit entry."""

    if price <= 0:
        raise HTTPException(status_code=422, detail="price must be greater than 0")
    if old_price is not None and old_price < price:
        raise HTTPException(status_code=422, detail="old_price must be greater than or equal to price")

    category = await db.scalar(select(MenuCategory).where(MenuCategory.id == category_id))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    image_url: str | None = None
    if photo is not None:
        if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=422, detail="Unsupported image type")
        body = await photo.read()
        if len(body) > 5 * 1024 * 1024:
            raise HTTPException(status_code=422, detail="Image exceeds 5 MB")
        object_key = (
            f"tenants/{request.state.tenant_id}/menu/{uuid.uuid4().hex}-{photo.filename or 'image'}"
        )
        image_url = await object_storage.upload_bytes(
            key=object_key,
            body=body,
            content_type=photo.content_type,
        )

    slug_base = _slugify(name)
    slug = slug_base
    suffix = 1
    while await db.scalar(select(MenuItem.id).where(MenuItem.slug == slug)) is not None:
        suffix += 1
        slug = f"{slug_base}-{suffix}"

    dish = MenuItem(
        category_id=category_id,
        slug=slug,
        sku=sku,
        name=name.strip(),
        description=description.strip() if description else None,
        price=price,
        old_price=old_price,
        weight_grams=weight_grams,
        calories=calories,
        image_url=image_url,
        tags=[item.strip() for item in tags.split(",")] if tags else [],
        allergens=[item.strip() for item in allergens.split(",")] if allergens else [],
        is_available=is_available,
        is_popular=is_popular,
        sort_order=sort_order,
    )
    db.add(dish)
    await db.flush()
    await write_audit_log(
        db,
        actor_user_id=getattr(request.state, "user_id", None),
        actor_role=getattr(request.state, "user_role", None),
        actor_ip=request.client.host if request.client else None,
        entity_type="menu_item",
        entity_id=str(dish.id),
        action="create",
        new_value={
            "name": dish.name,
            "slug": dish.slug,
            "price": str(dish.price),
            "category_id": dish.category_id,
        },
    )
    await db.refresh(dish)
    return DishOut.model_validate(dish)
