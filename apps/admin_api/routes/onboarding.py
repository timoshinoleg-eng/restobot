"""Onboarding wizard endpoints."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import String, cast, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.middleware import get_db
from backend.auth.bootstrap import ensure_role_catalog
from backend.auth.models import EmployeeUser
from backend.auth.permissions import PERMISSION_MATRIX, require_permission
from backend.auth.security import create_refresh_token, hash_password
from backend.menu.models import MenuCategory, MenuItem
from backend.orders.service import create_order, order_to_schema
from backend.schemas.auth import TenantOut, TokenResponse, UserOut
from backend.schemas.onboarding import (
    MenuUploadRequest,
    OnboardingStartRequest,
    OnboardingStartResponse,
    OnboardingStepResponse,
    PaymentSetupRequest,
    RestaurantInfoRequest,
    TelegramSetupRequest,
    TestOrderResponse,
)
from backend.settings.models import TenantSettings
from shared.config import get_settings
from shared.database import AsyncSessionLocal, Base, _tenant_tables
from shared.jwt_utils import create_access_token
from shared.models import Tenant

router = APIRouter(prefix="/admin/v1/onboarding", tags=["onboarding"])
settings = get_settings()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9а-яё]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "restaurant"


async def _load_tenant(db: AsyncSession, tenant_key: str) -> Tenant:
    tenant = await db.scalar(
        select(Tenant).where(or_(Tenant.slug == tenant_key, cast(Tenant.id, String) == tenant_key))
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post("/start", response_model=OnboardingStartResponse, status_code=status.HTTP_201_CREATED)
async def onboarding_start(body: OnboardingStartRequest) -> OnboardingStartResponse:
    session = AsyncSessionLocal()
    try:
        slug = _slugify(body.restaurant_name)
        existing = await session.scalar(select(Tenant).where(Tenant.slug == slug))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Tenant slug already exists")

        tenant = Tenant(
            name=body.restaurant_name,
            slug=slug,
            phone=body.phone,
            email=body.owner_email,
            status="active",
            billing_status="trial",
            onboarding_step="restaurant_info",
            trial_starts_at=datetime.now(timezone.utc),
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        session.add(tenant)
        await session.flush()

        tenant_key = str(tenant.id)
        tenant_schema = settings.get_tenant_schema(tenant_key)
        await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {tenant_schema}"))
        await session.execute(text(f"SET LOCAL search_path TO {tenant_schema}, shared"))
        async with session.bind.begin() as connection:
            await connection.execute(text(f"SET search_path TO {tenant_schema}, shared"))
            await connection.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_tenant_tables())
            )
        await ensure_role_catalog(session)

        owner = EmployeeUser(
            email=body.owner_email,
            phone=body.phone,
            password_hash=hash_password(body.owner_password),
            full_name=body.owner_name,
            role_code="owner",
            is_active=True,
        )
        session.add(owner)
        session.add(
            TenantSettings(
                restaurant_display_name=body.restaurant_name,
                phone=body.phone,
                support_email=body.owner_email,
            )
        )
        await session.flush()
        await session.commit()

        permissions = sorted(PERMISSION_MATRIX["owner"])
        access_token = create_access_token(user_id=owner.id, tenant_id=tenant_key, role="owner")
        refresh_token = create_refresh_token(user_id=owner.id, tenant_id=tenant_key, role="owner")
        token = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=60 * 60,
            user=UserOut(id=owner.id, full_name=owner.full_name, email=owner.email, role="owner"),
            tenant=TenantOut(
                id=tenant.id,
                slug=tenant.slug or tenant_key,
                name=tenant.name,
                billing_status=tenant.billing_status,
                trial_ends_at=tenant.trial_ends_at,
            ),
            permissions=permissions,
        )
        return OnboardingStartResponse(
            tenant_slug=tenant.slug or tenant_key,
            onboarding_step="restaurant_info",
            trial_ends_at=tenant.trial_ends_at or datetime.now(timezone.utc),
            token=token,
        )
    finally:
        await session.close()


@router.post(
    "/restaurant-info",
    response_model=OnboardingStepResponse,
    dependencies=[Depends(require_permission("onboarding.write"))],
)
async def onboarding_restaurant_info(
    body: RestaurantInfoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OnboardingStepResponse:
    tenant = await _load_tenant(db, request.state.tenant_id)
    settings_row = await db.scalar(select(TenantSettings).limit(1))
    if settings_row is None:
        settings_row = TenantSettings(restaurant_display_name=tenant.name)
        db.add(settings_row)
        await db.flush()
    settings_row.restaurant_display_name = body.restaurant_display_name
    settings_row.legal_name = body.legal_name
    settings_row.phone = body.phone
    settings_row.support_email = body.support_email
    settings_row.address_json = body.address_json
    settings_row.working_hours_json = body.working_hours_json
    tenant.onboarding_step = "menu_upload"
    await db.flush()
    return OnboardingStepResponse(onboarding_step="menu_upload")


@router.post(
    "/menu-upload",
    response_model=OnboardingStepResponse,
    dependencies=[Depends(require_permission("menu.write"))],
)
async def onboarding_menu_upload(
    body: MenuUploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OnboardingStepResponse:
    tenant = await _load_tenant(db, request.state.tenant_id)
    for category_payload in body.categories:
        category = MenuCategory(
            name=category_payload.name,
            slug=_slugify(category_payload.name),
        )
        db.add(category)
        await db.flush()
        for item_payload in category_payload.items:
            db.add(
                MenuItem(
                    category_id=category.id,
                    slug=_slugify(item_payload.name),
                    name=item_payload.name,
                    description=item_payload.description,
                    price=item_payload.price,
                    is_available=True,
                    is_popular=False,
                )
            )
    tenant.onboarding_step = "telegram_setup"
    await db.flush()
    return OnboardingStepResponse(onboarding_step="telegram_setup")


@router.post(
    "/telegram-setup",
    response_model=OnboardingStepResponse,
    dependencies=[Depends(require_permission("onboarding.write"))],
)
async def onboarding_telegram_setup(
    body: TelegramSetupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OnboardingStepResponse:
    tenant = await _load_tenant(db, request.state.tenant_id)
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"https://api.telegram.org/bot{body.bot_token}/getMe")
        if response.status_code >= 400:
            raise HTTPException(status_code=422, detail="Invalid Telegram bot token")
    settings_row = await db.scalar(select(TenantSettings).limit(1))
    if settings_row is None:
        settings_row = TenantSettings(restaurant_display_name=tenant.name)
        db.add(settings_row)
        await db.flush()
    settings_row.telegram_bot_token_ref = body.bot_token
    tenant.onboarding_step = "payment_setup"
    await db.flush()
    return OnboardingStepResponse(onboarding_step="payment_setup")


@router.post(
    "/payment-setup",
    response_model=OnboardingStepResponse,
    dependencies=[Depends(require_permission("onboarding.write"))],
)
async def onboarding_payment_setup(
    body: PaymentSetupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OnboardingStepResponse:
    tenant = await _load_tenant(db, request.state.tenant_id)
    settings_row = await db.scalar(select(TenantSettings).limit(1))
    if settings_row is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    if not body.skip:
        settings_row.yookassa_shop_id = body.yookassa_shop_id
        settings_row.yookassa_secret_ref = body.yookassa_secret_key
    tenant.onboarding_step = "test_order"
    await db.flush()
    return OnboardingStepResponse(onboarding_step="test_order")


@router.post(
    "/test-order",
    response_model=TestOrderResponse,
    dependencies=[Depends(require_permission("orders.write"))],
)
async def onboarding_test_order(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TestOrderResponse:
    tenant = await _load_tenant(db, request.state.tenant_id)
    dish = await db.scalar(select(MenuItem).where(MenuItem.is_available.is_(True)).limit(1))
    if dish is None:
        raise HTTPException(status_code=422, detail="No menu items available for test order")
    order = await create_order(
        db,
        tenant_id=request.state.tenant_id,
        source_channel="admin",
        actor_user_id=getattr(request.state, "user_id", None),
        actor_role=getattr(request.state, "user_role", None),
        actor_ip=request.client.host if request.client else None,
        customer_name="Test Customer",
        phone="+79990000000",
        order_type="pickup",
        address=None,
        comment="Onboarding test order",
        payment_method="cash",
        items=[{"menu_item_id": dish.id, "quantity": 1}],
        status="accepted",
    )
    tenant.onboarding_step = "completed"
    await db.flush()
    return TestOrderResponse(
        order_id=order.id,
        order_number=order.order_number,
        onboarding_step="completed",
    )


@router.post(
    "/complete",
    response_model=OnboardingStepResponse,
    dependencies=[Depends(require_permission("onboarding.write"))],
)
async def onboarding_complete(request: Request, db: AsyncSession = Depends(get_db)) -> OnboardingStepResponse:
    tenant = await _load_tenant(db, request.state.tenant_id)
    tenant.onboarding_step = "completed"
    tenant.onboarding_completed_at = datetime.now(timezone.utc)
    await db.flush()
    return OnboardingStepResponse(onboarding_step="completed", completed=True)
