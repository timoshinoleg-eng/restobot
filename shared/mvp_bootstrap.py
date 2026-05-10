"""Tenant bootstrap helpers and admin/public MVP operations."""

import logging
import secrets
from typing import Any, Optional

from fastapi import HTTPException
from passlib.context import CryptContext

from shared.config import get_settings
from shared.consent import attach_telegram_consent_to_user, record_user_consent
from shared.database import get_raw_pool
from shared.jwt_utils import create_access_token
from shared.sql_utils import format_sql

settings = get_settings()
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


TENANT_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS {}.users (
        id BIGSERIAL PRIMARY KEY,
        external_id VARCHAR(128) UNIQUE,
        telegram_id VARCHAR(64),
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(20),
        email VARCHAR(255),
        loyalty_points NUMERIC(12,2) NOT NULL DEFAULT 0,
        role VARCHAR(20) NOT NULL DEFAULT 'user',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        password_hash VARCHAR(255),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.menu_categories (
        id BIGSERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        emoji VARCHAR(16),
        sort_order INT NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.menu_items (
        id BIGSERIAL PRIMARY KEY,
        category_id BIGINT REFERENCES {}.menu_categories(id) ON DELETE SET NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        price NUMERIC(12,2) NOT NULL,
        image_url TEXT,
        is_available BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order INT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.restaurant_settings (
        id BIGSERIAL PRIMARY KEY,
        restaurant_name VARCHAR(255) NOT NULL,
        min_order_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        delivery_radius NUMERIC(12,2) DEFAULT 0,
        setup_token VARCHAR(64),
        vat_code INT NOT NULL DEFAULT 1,
        currency VARCHAR(8) NOT NULL DEFAULT 'RUB',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.orders (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES {}.users(id),
        order_number VARCHAR(64) NOT NULL UNIQUE,
        type VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'new',
        payment_status VARCHAR(32) NOT NULL DEFAULT 'pending',
        payment_method VARCHAR(32) NOT NULL DEFAULT 'cash',
        amount NUMERIC(12,2) NOT NULL,
        delivery_fee NUMERIC(12,2) NOT NULL DEFAULT 0,
        discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        loyalty_used NUMERIC(12,2) NOT NULL DEFAULT 0,
        items_json JSONB NOT NULL,
        address TEXT,
        phone VARCHAR(20),
        comment TEXT,
        scheduled_for TIMESTAMPTZ,
        payment_id VARCHAR(128),
        payment_provider VARCHAR(64),
        payment_idempotency_key VARCHAR(128),
        idempotency_key VARCHAR(64) UNIQUE,
        paid_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.loyalty_transactions (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES {}.users(id),
        order_id BIGINT REFERENCES {}.orders(id) ON DELETE SET NULL,
        type VARCHAR(20) NOT NULL,
        points NUMERIC(12,2) NOT NULL,
        balance_after NUMERIC(12,2) NOT NULL,
        description TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.ingredients (
        id BIGSERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        unit VARCHAR(20) NOT NULL DEFAULT 'г',
        current_stock NUMERIC(12,2) NOT NULL DEFAULT 0,
        reserved_stock NUMERIC(12,2) NOT NULL DEFAULT 0,
        min_stock NUMERIC(12,2) NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.recipes (
        id BIGSERIAL PRIMARY KEY,
        menu_item_id BIGINT NOT NULL REFERENCES {}.menu_items(id) ON DELETE CASCADE,
        ingredient_id BIGINT NOT NULL REFERENCES {}.ingredients(id) ON DELETE CASCADE,
        grams_needed NUMERIC(12,2) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.stock_movements (
        id BIGSERIAL PRIMARY KEY,
        ingredient_id BIGINT NOT NULL REFERENCES {}.ingredients(id) ON DELETE CASCADE,
        type VARCHAR(20) NOT NULL,
        quantity NUMERIC(12,2) NOT NULL,
        comment TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.menu_item_modifiers (
        id BIGSERIAL PRIMARY KEY,
        menu_item_id BIGINT NOT NULL REFERENCES {}.menu_items(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        required BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.modifier_options (
        id BIGSERIAL PRIMARY KEY,
        modifier_id BIGINT NOT NULL REFERENCES {}.menu_item_modifiers(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        price NUMERIC(12,2) NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.tables (
        id BIGSERIAL PRIMARY KEY,
        number VARCHAR(10) NOT NULL,
        capacity INT NOT NULL DEFAULT 4,
        location VARCHAR(100),
        status VARCHAR(20) NOT NULL DEFAULT 'available',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.reservations (
        id BIGSERIAL PRIMARY KEY,
        table_id BIGINT NOT NULL REFERENCES {}.tables(id) ON DELETE CASCADE,
        user_id BIGINT NOT NULL REFERENCES {}.users(id),
        guest_name VARCHAR(255) NOT NULL,
        guest_phone VARCHAR(20) NOT NULL,
        start_time TIMESTAMPTZ NOT NULL,
        end_time TIMESTAMPTZ NOT NULL,
        guests_count INT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        comment TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.payment_dlq (
        id BIGSERIAL PRIMARY KEY,
        event_type VARCHAR(64) NOT NULL,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.payment_webhook_events (
        id BIGSERIAL PRIMARY KEY,
        payment_id VARCHAR(128) NOT NULL,
        event_type VARCHAR(64) NOT NULL,
        payload JSONB NOT NULL,
        processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (payment_id, event_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.user_consents (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES {}.users(id) ON DELETE SET NULL,
        telegram_user_id BIGINT,
        external_id VARCHAR(128),
        consent_version INT NOT NULL,
        consent_hash VARCHAR(64) NOT NULL,
        source VARCHAR(32) NOT NULL,
        agreed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        revoked_at TIMESTAMPTZ
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_consents_external_active
    ON {}.user_consents (consent_version, source, external_id)
    WHERE external_id IS NOT NULL AND revoked_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_user_consents_user_active
    ON {}.user_consents (user_id, consent_version)
    WHERE revoked_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_user_consents_telegram_active
    ON {}.user_consents (telegram_user_id, consent_version)
    WHERE telegram_user_id IS NOT NULL AND revoked_at IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.audit_log (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        user_id BIGINT,
        action VARCHAR(32) NOT NULL,
        table_name VARCHAR(64) NOT NULL,
        record_id BIGINT,
        old_values JSONB,
        new_values JSONB,
        ip_address INET,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created ON {}.audit_log (tenant_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_log_user ON {}.audit_log (user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_log_table_action ON {}.audit_log (table_name, action)
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.loyalty_settings (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL UNIQUE,
        bonus_percent NUMERIC(5,2) NOT NULL DEFAULT 5.0,
        max_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 30.0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.working_hours (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
        open_time TIME,
        close_time TIME,
        is_closed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (tenant_id, day_of_week)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {}.onboarding_state (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL UNIQUE,
        current_step VARCHAR(32) NOT NULL DEFAULT 'welcome',
        completed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]


async def ensure_tenant_schema(tenant_id: str) -> str:
    """Create a tenant schema and all required MVP tables if they do not exist."""
    tenant_schema = settings.get_tenant_schema(tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{tenant_schema}"')
            for statement in TENANT_SCHEMA_STATEMENTS:
                placeholder_count = statement.count("{}")
                if placeholder_count == 0:
                    await conn.execute(statement)
                    continue
                await conn.execute(format_sql(statement, *([tenant_schema] * placeholder_count)))
    return tenant_schema


async def require_existing_tenant_schema(tenant_id: str) -> str:
    """Return an existing tenant schema and fail closed for unknown tenants."""
    tenant_schema = settings.get_tenant_schema(tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        tenant_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM shared.tenants
                WHERE slug = $1 AND status = 'active'
            )
            """,
            tenant_id,
        )
        schema_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM information_schema.schemata
                WHERE schema_name = $1
            )
            """,
            tenant_schema,
        )

    if not tenant_exists or not schema_exists:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant_schema


async def bootstrap_tenant(
    tenant_id: str,
    restaurant_name: str,
    admin_name: str,
    admin_email: Optional[str],
    admin_phone: Optional[str],
    min_order_amount: float,
) -> dict[str, Any]:
    """Create or update the shared tenant record and seed a tenant schema."""
    tenant_schema = await ensure_tenant_schema(tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            tenant_row = await conn.fetchrow(
                """
                INSERT INTO shared.tenants (slug, name, email, phone, status)
                VALUES ($1, $2, $3, $4, 'active')
                ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    updated_at = NOW()
                RETURNING id, slug, name
                """,
                tenant_id,
                restaurant_name,
                admin_email,
                admin_phone,
            )

            admin_row = await conn.fetchrow(
                format_sql(
                    """
                    INSERT INTO {}.users (external_id, name, email, phone, role)
                    VALUES ($1, $2, $3, $4, 'admin')
                    ON CONFLICT (external_id) DO UPDATE
                    SET name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        role = 'admin',
                        updated_at = NOW()
                    RETURNING id, name
                    """,
                    tenant_schema,
                ),
                f"admin:{tenant_id}",
                admin_name,
                admin_email,
                admin_phone,
            )

            # Check if admin already has a password hash (first-login already done)
            existing_admin_hash = await conn.fetchval(
                format_sql(
                    "SELECT password_hash FROM {}.users WHERE external_id = $1",
                    tenant_schema,
                ),
                f"admin:{tenant_id}",
            )

            if existing_admin_hash:
                # Admin already set up — do not overwrite setup_token
                setup_token_raw = None
                settings_row = await conn.fetchrow(
                    format_sql(
                        """
                        INSERT INTO {}.restaurant_settings (id, restaurant_name, min_order_amount, setup_token)
                        VALUES (1, $1, $2, NULL)
                        ON CONFLICT (id) DO UPDATE
                        SET restaurant_name = EXCLUDED.restaurant_name,
                            min_order_amount = EXCLUDED.min_order_amount,
                            updated_at = NOW()
                        RETURNING restaurant_name, min_order_amount
                        """,
                        tenant_schema,
                    ),
                    restaurant_name,
                    min_order_amount,
                )
            else:
                # Generate a setup token for first-login protection
                setup_token_raw = secrets.token_urlsafe(32)
                setup_token_hash = pwd_context.hash(setup_token_raw)
                settings_row = await conn.fetchrow(
                    format_sql(
                        """
                        INSERT INTO {}.restaurant_settings (id, restaurant_name, min_order_amount, setup_token)
                        VALUES (1, $1, $2, $3)
                        ON CONFLICT (id) DO UPDATE
                        SET restaurant_name = EXCLUDED.restaurant_name,
                            min_order_amount = EXCLUDED.min_order_amount,
                            setup_token = EXCLUDED.setup_token,
                            updated_at = NOW()
                        RETURNING restaurant_name, min_order_amount
                        """,
                        tenant_schema,
                    ),
                    restaurant_name,
                    min_order_amount,
                    setup_token_hash,
                )

            table_exists = await conn.fetchval(
                format_sql("SELECT EXISTS(SELECT 1 FROM {}.tables WHERE number = '1')", tenant_schema)
            )
            if not table_exists:
                await conn.execute(
                    format_sql(
                        """
                        INSERT INTO {}.tables (number, capacity, location, status)
                        VALUES ('1', 4, 'Main hall', 'available')
                        """,
                        tenant_schema,
                    )
                )

            # Seed default working hours
            for dow in range(7):
                await conn.execute(
                    format_sql(
                        """
                        INSERT INTO {}.working_hours
                        (tenant_id, day_of_week, open_time, close_time, is_closed)
                        VALUES ($1, $2, '10:00', '22:00', FALSE)
                        ON CONFLICT (tenant_id, day_of_week) DO NOTHING
                        """,
                        tenant_schema,
                    ),
                    tenant_id,
                    dow,
                )

            # Seed onboarding state
            await conn.execute(
                format_sql(
                    """
                    INSERT INTO {}.onboarding_state (tenant_id, current_step)
                    VALUES ($1, 'welcome')
                    ON CONFLICT (tenant_id) DO NOTHING
                    """,
                    tenant_schema,
                ),
                tenant_id,
            )

    assert tenant_row is not None
    assert admin_row is not None
    assert settings_row is not None
    admin_token = create_access_token(
        user_id=int(admin_row["id"]),
        tenant_id=tenant_id,
        role="admin",
    )
    return {
        "tenant_id": tenant_id,
        "tenant_schema": tenant_schema,
        "tenant_db_id": int(tenant_row["id"]),
        "restaurant_name": settings_row["restaurant_name"],
        "admin_user_id": int(admin_row["id"]),
        "admin_token": admin_token,
        "setup_token": setup_token_raw,
    }


async def replace_menu(
    tenant_id: str,
    categories: list[dict[str, Any]],
    min_order_amount: Optional[float] = None,
) -> dict[str, Any]:
    """Replace tenant menu atomically."""
    tenant_schema = await ensure_tenant_schema(tenant_id)
    pool = await get_raw_pool()
    categories_written = 0
    items_written = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(format_sql("DELETE FROM {}.menu_items", tenant_schema))
            await conn.execute(format_sql("DELETE FROM {}.menu_categories", tenant_schema))

            if min_order_amount is not None:
                await conn.execute(
                    format_sql(
                        """
                        UPDATE {}.restaurant_settings
                        SET min_order_amount = $1, updated_at = NOW()
                        """,
                        tenant_schema,
                    ),
                    min_order_amount,
                )

            for category in categories:
                category_row = await conn.fetchrow(
                    format_sql(
                        """
                        INSERT INTO {}.menu_categories (name, emoji, sort_order, is_active)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                        """,
                        tenant_schema,
                    ),
                    category["name"],
                    category.get("emoji"),
                    category.get("sort_order", categories_written),
                    category.get("is_active", True),
                )
                categories_written += 1
                assert category_row is not None
                for item_index, item in enumerate(category.get("items", [])):
                    await conn.execute(
                        format_sql(
                            """
                            INSERT INTO {}.menu_items (
                                category_id, name, description, price, image_url, is_available, sort_order
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            """,
                            tenant_schema,
                        ),
                        category_row["id"],
                        item["name"],
                        item.get("description"),
                        item["price"],
                        item.get("image_url"),
                        item.get("is_available", True),
                        item.get("sort_order", item_index),
                    )
                    items_written += 1

    return {
        "tenant_id": tenant_id,
        "categories_written": categories_written,
        "items_written": items_written,
    }


async def create_widget_session(
    tenant_id: str,
    external_id: str,
    name: str,
    phone: Optional[str],
    email: Optional[str],
    consent_accepted: bool = False,
) -> dict[str, Any]:
    """Create or update a widget user session and return a JWT."""
    tenant_schema = await require_existing_tenant_schema(tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            format_sql(
                """
                INSERT INTO {}.users (external_id, name, phone, email, role)
                VALUES ($1, $2, $3, $4, 'user')
                ON CONFLICT (external_id) DO UPDATE
                SET name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    updated_at = NOW()
                RETURNING id, loyalty_points
                """,
                tenant_schema,
            ),
            external_id,
            name,
            phone,
            email,
        )

    assert user_row is not None
    telegram_user_id: Optional[int] = None
    if external_id.startswith("tg-"):
        try:
            telegram_user_id = int(external_id[3:])
        except ValueError:
            telegram_user_id = None

    await attach_telegram_consent_to_user(
        tenant_schema,
        user_id=int(user_row["id"]),
        telegram_user_id=telegram_user_id,
        external_id=external_id,
    )
    if consent_accepted:
        await record_user_consent(
            tenant_schema,
            user_id=int(user_row["id"]),
            telegram_user_id=telegram_user_id,
            external_id=external_id,
            source="widget",
        )

    access_token = create_access_token(
        user_id=int(user_row["id"]),
        tenant_id=tenant_id,
        role="user",
    )
    return {
        "tenant_id": tenant_id,
        "user_id": int(user_row["id"]),
        "loyalty_points": float(user_row["loyalty_points"]),
        "access_token": access_token,
    }


async def update_order_status(
    tenant_id: str,
    order_id: int,
    status_value: str,
    payment_status: Optional[str],
) -> dict[str, Any]:
    """Update order status from the admin API."""
    tenant_schema = settings.get_tenant_schema(tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            format_sql(
                """
                UPDATE {}.orders
                SET status = $1,
                    payment_status = COALESCE($2, payment_status)
                WHERE id = $3
                RETURNING id, order_number, status, payment_status
                """,
                tenant_schema,
            ),
            status_value,
            payment_status,
            order_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "id": int(row["id"]),
        "order_number": row["order_number"],
        "status": row["status"],
        "payment_status": row["payment_status"],
    }
