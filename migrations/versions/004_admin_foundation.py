"""Add admin SaaS foundation tables and columns.

Revision ID: 004
Revises: 003
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Sequence, Union

from alembic import context, op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_schema() -> str:
    tenant_schema = context.config.get_main_option("tenant_schema")
    if not tenant_schema:
        tenant_schema = "tenant_default"
    return tenant_schema


def _execute_many(statements: Iterable[str]) -> None:
    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    tenant_schema = _tenant_schema()
    op.execute(f"SET search_path TO {tenant_schema}, shared")

    _execute_many(
        [
            """
            CREATE TABLE IF NOT EXISTS roles (
                code VARCHAR(32) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS role_permissions (
                id BIGSERIAL PRIMARY KEY,
                role_code VARCHAR(32) NOT NULL REFERENCES roles(code) ON DELETE CASCADE,
                permission_code VARCHAR(64) NOT NULL,
                CONSTRAINT uq_role_permissions_permission_code UNIQUE (permission_code)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS employee_users (
                id BIGSERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                role_code VARCHAR(32) NOT NULL REFERENCES roles(code),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                last_login_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_employee_users_email UNIQUE (email)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tenant_settings (
                id BIGSERIAL PRIMARY KEY,
                restaurant_display_name VARCHAR(255) NOT NULL,
                legal_name VARCHAR(255),
                phone VARCHAR(20),
                support_email VARCHAR(255),
                bot_name VARCHAR(255) NOT NULL DEFAULT 'RestoBot',
                greeting_text TEXT,
                ai_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                web_widget_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                timezone VARCHAR(50) NOT NULL DEFAULT 'Europe/Moscow',
                currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
                min_order_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                delivery_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                pickup_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                address_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                working_hours_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                yookassa_shop_id VARCHAR(128),
                yookassa_secret_ref VARCHAR(255),
                telegram_bot_token_ref VARCHAR(255),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL PRIMARY KEY,
                actor_user_id BIGINT,
                actor_role VARCHAR(32),
                actor_ip INET,
                entity_type VARCHAR(64) NOT NULL,
                entity_id VARCHAR(64) NOT NULL,
                action VARCHAR(32) NOT NULL,
                old_value JSONB,
                new_value JSONB,
                reason VARCHAR(255),
                request_id UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS menu_categories (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                emoji VARCHAR(16),
                sort_order INTEGER NOT NULL DEFAULT 100,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS slug VARCHAR(255)
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS description TEXT
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS emoji VARCHAR(16)
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 100
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_categories_slug ON menu_categories (slug)
            """,
            """
            CREATE TABLE IF NOT EXISTS menu_items (
                id BIGSERIAL PRIMARY KEY,
                category_id BIGINT NOT NULL REFERENCES menu_categories(id),
                slug VARCHAR(255) NOT NULL UNIQUE,
                sku VARCHAR(64),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price NUMERIC(12,2) NOT NULL,
                old_price NUMERIC(12,2),
                weight_grams INTEGER,
                calories INTEGER,
                image_url VARCHAR(1024),
                tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                allergens JSONB NOT NULL DEFAULT '[]'::jsonb,
                is_available BOOLEAN NOT NULL DEFAULT TRUE,
                is_popular BOOLEAN NOT NULL DEFAULT FALSE,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                sort_order INTEGER NOT NULL DEFAULT 100,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS category_id BIGINT REFERENCES menu_categories(id)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS slug VARCHAR(255)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS sku VARCHAR(64)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS name VARCHAR(255)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS description TEXT
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS price NUMERIC(12,2)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS old_price NUMERIC(12,2)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS weight_grams INTEGER
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS calories INTEGER
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS image_url VARCHAR(1024)
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS allergens JSONB NOT NULL DEFAULT '[]'::jsonb
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT TRUE
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_popular BOOLEAN NOT NULL DEFAULT FALSE
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 100
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_items_slug ON menu_items (slug)
            """,
            """
            CREATE TABLE IF NOT EXISTS menu_item_modifiers (
                id BIGSERIAL PRIMARY KEY,
                menu_item_id BIGINT NOT NULL REFERENCES menu_items(id),
                name VARCHAR(255) NOT NULL,
                selection_type VARCHAR(16) NOT NULL DEFAULT 'single',
                min_selected INTEGER NOT NULL DEFAULT 0,
                max_selected INTEGER NOT NULL DEFAULT 1,
                required BOOLEAN NOT NULL DEFAULT FALSE,
                sort_order INTEGER NOT NULL DEFAULT 100,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE menu_item_modifiers ADD COLUMN IF NOT EXISTS selection_type VARCHAR(16) NOT NULL DEFAULT 'single'
            """,
            """
            ALTER TABLE menu_item_modifiers ADD COLUMN IF NOT EXISTS min_selected INTEGER NOT NULL DEFAULT 0
            """,
            """
            ALTER TABLE menu_item_modifiers ADD COLUMN IF NOT EXISTS max_selected INTEGER NOT NULL DEFAULT 1
            """,
            """
            ALTER TABLE menu_item_modifiers ADD COLUMN IF NOT EXISTS required BOOLEAN NOT NULL DEFAULT FALSE
            """,
            """
            ALTER TABLE menu_item_modifiers ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 100
            """,
            """
            ALTER TABLE menu_item_modifiers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            CREATE TABLE IF NOT EXISTS modifier_options (
                id BIGSERIAL PRIMARY KEY,
                modifier_id BIGINT NOT NULL REFERENCES menu_item_modifiers(id),
                name VARCHAR(255) NOT NULL,
                price NUMERIC(12,2) NOT NULL DEFAULT 0,
                is_available BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 100,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE modifier_options ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT TRUE
            """,
            """
            ALTER TABLE modifier_options ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 100
            """,
            """
            ALTER TABLE modifier_options ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            CREATE TABLE IF NOT EXISTS menu_stop_list (
                id BIGSERIAL PRIMARY KEY,
                menu_item_id BIGINT NOT NULL REFERENCES menu_items(id),
                reason VARCHAR(255),
                starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                ends_at TIMESTAMPTZ,
                created_by BIGINT REFERENCES employee_users(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS guest_sessions (
                id UUID PRIMARY KEY,
                source_channel VARCHAR(32) NOT NULL DEFAULT 'web_widget',
                source_url VARCHAR(1024),
                consent_personal_data BOOLEAN NOT NULL DEFAULT FALSE,
                consent_marketing BOOLEAN NOT NULL DEFAULT FALSE,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS source_channel VARCHAR(32)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS guest_session_id UUID REFERENCES guest_sessions(id)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS phone VARCHAR(20)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS address VARCHAR(500)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS comment TEXT
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal NUMERIC(12,2)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(12,2)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee NUMERIC(12,2)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_amount NUMERIC(12,2)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS loyalty_used NUMERIC(12,2)
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ
            """,
            """
            ALTER TABLE orders ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ
            """,
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id BIGSERIAL PRIMARY KEY,
                order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                menu_item_id BIGINT REFERENCES menu_items(id),
                item_name_snapshot VARCHAR(255) NOT NULL,
                sku_snapshot VARCHAR(64),
                unit_price NUMERIC(12,2) NOT NULL,
                quantity NUMERIC(12,3) NOT NULL,
                line_total NUMERIC(12,2) NOT NULL,
                modifiers_json JSONB NOT NULL DEFAULT '[]'::jsonb
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS order_events (
                id BIGSERIAL PRIMARY KEY,
                order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                event_type VARCHAR(32) NOT NULL,
                from_status VARCHAR(32),
                to_status VARCHAR(32),
                actor_type VARCHAR(32) NOT NULL,
                actor_id BIGINT,
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS loyalty_accounts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                balance NUMERIC(12,2) NOT NULL DEFAULT 0,
                tier VARCHAR(32) NOT NULL DEFAULT 'base',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE loyalty_accounts ADD COLUMN IF NOT EXISTS balance NUMERIC(12,2) NOT NULL DEFAULT 0
            """,
            """
            ALTER TABLE loyalty_accounts ADD COLUMN IF NOT EXISTS tier VARCHAR(32) NOT NULL DEFAULT 'base'
            """,
            """
            ALTER TABLE loyalty_accounts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            ALTER TABLE loyalty_accounts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """,
            """
            CREATE TABLE IF NOT EXISTS loyalty_transactions (
                id BIGSERIAL PRIMARY KEY,
                account_id BIGINT NOT NULL REFERENCES loyalty_accounts(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                order_id BIGINT REFERENCES orders(id),
                type VARCHAR(32) NOT NULL,
                points NUMERIC(12,2) NOT NULL,
                balance_after NUMERIC(12,2) NOT NULL,
                description VARCHAR(255),
                source_channel VARCHAR(32),
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS account_id BIGINT REFERENCES loyalty_accounts(id) ON DELETE CASCADE
            """,
            """
            ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS user_id BIGINT
            """,
            """
            ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS order_id BIGINT REFERENCES orders(id)
            """,
            """
            ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS balance_after NUMERIC(12,2)
            """,
            """
            ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS source_channel VARCHAR(32)
            """,
            """
            ALTER TABLE loyalty_transactions ADD COLUMN IF NOT EXISTS created_by BIGINT
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_orders_created_at_desc
            ON orders (created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_orders_status_created_at
            ON orders (status, created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_orders_source_channel
            ON orders (source_channel)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_order_items_menu_item_id
            ON order_items (menu_item_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at
            ON audit_logs (created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_menu_items_slug
            ON menu_items (slug)
            """,
            """
            ALTER TABLE shared.tenants ADD COLUMN IF NOT EXISTS slug VARCHAR(100)
            """,
            """
            ALTER TABLE shared.tenants ADD COLUMN IF NOT EXISTS trial_starts_at TIMESTAMPTZ
            """,
            """
            ALTER TABLE shared.tenants ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ
            """,
            """
            ALTER TABLE shared.tenants ADD COLUMN IF NOT EXISTS billing_status VARCHAR(32) DEFAULT 'trial'
            """,
            """
            ALTER TABLE shared.tenants ADD COLUMN IF NOT EXISTS onboarding_step VARCHAR(32)
            """,
            """
            ALTER TABLE shared.tenants ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_shared_tenants_slug
            ON shared.tenants (slug)
            """,
            """
            INSERT INTO roles (code, name, description)
            VALUES
                ('owner', 'Owner', 'Full tenant access'),
                ('manager', 'Manager', 'Operations and settings access'),
                ('operator', 'Operator', 'Order operations access'),
                ('cook', 'Cook', 'Kitchen workflow access')
            ON CONFLICT (code) DO NOTHING
            """,
            """
            INSERT INTO role_permissions (role_code, permission_code)
            VALUES
                ('owner', '*'),
                ('manager', 'dashboard.read'),
                ('manager', 'menu.read'),
                ('manager', 'menu.write'),
                ('manager', 'orders.read'),
                ('manager', 'orders.write'),
                ('manager', 'settings.read'),
                ('manager', 'settings.write'),
                ('manager', 'audit.read'),
                ('manager', 'onboarding.write'),
                ('operator', 'dashboard.read'),
                ('operator', 'menu.read'),
                ('operator', 'orders.read'),
                ('operator', 'orders.write'),
                ('cook', 'orders.read'),
                ('cook', 'orders.status.kitchen')
            ON CONFLICT (permission_code) DO NOTHING
            """
        ]
    )


def downgrade() -> None:
    tenant_schema = _tenant_schema()
    op.execute(f"SET search_path TO {tenant_schema}, shared")
    _execute_many(
        [
            "DROP INDEX IF EXISTS ix_shared_tenants_slug",
            "ALTER TABLE shared.tenants DROP COLUMN IF EXISTS onboarding_completed_at",
            "ALTER TABLE shared.tenants DROP COLUMN IF EXISTS onboarding_step",
            "ALTER TABLE shared.tenants DROP COLUMN IF EXISTS billing_status",
            "ALTER TABLE shared.tenants DROP COLUMN IF EXISTS trial_ends_at",
            "ALTER TABLE shared.tenants DROP COLUMN IF EXISTS trial_starts_at",
            "ALTER TABLE shared.tenants DROP COLUMN IF EXISTS slug",
            "DROP INDEX IF EXISTS ix_menu_items_slug",
            "DROP INDEX IF EXISTS ix_audit_logs_created_at",
            "DROP INDEX IF EXISTS ix_order_items_menu_item_id",
            "DROP INDEX IF EXISTS ix_orders_source_channel",
            "DROP INDEX IF EXISTS ix_orders_status_created_at",
            "DROP INDEX IF EXISTS ix_orders_created_at_desc",
            "DROP TABLE IF EXISTS loyalty_transactions",
            "DROP TABLE IF EXISTS loyalty_accounts",
            "DROP TABLE IF EXISTS order_events",
            "DROP TABLE IF EXISTS order_items",
            "ALTER TABLE orders DROP COLUMN IF EXISTS closed_at",
            "ALTER TABLE orders DROP COLUMN IF EXISTS paid_at",
            "ALTER TABLE orders DROP COLUMN IF EXISTS loyalty_used",
            "ALTER TABLE orders DROP COLUMN IF EXISTS total_amount",
            "ALTER TABLE orders DROP COLUMN IF EXISTS delivery_fee",
            "ALTER TABLE orders DROP COLUMN IF EXISTS discount_amount",
            "ALTER TABLE orders DROP COLUMN IF EXISTS subtotal",
            "ALTER TABLE orders DROP COLUMN IF EXISTS comment",
            "ALTER TABLE orders DROP COLUMN IF EXISTS address",
            "ALTER TABLE orders DROP COLUMN IF EXISTS phone",
            "ALTER TABLE orders DROP COLUMN IF EXISTS guest_session_id",
            "ALTER TABLE orders DROP COLUMN IF EXISTS customer_name",
            "ALTER TABLE orders DROP COLUMN IF EXISTS source_channel",
            "DROP TABLE IF EXISTS guest_sessions",
            "DROP TABLE IF EXISTS menu_stop_list",
            "DROP TABLE IF EXISTS modifier_options",
            "DROP TABLE IF EXISTS menu_item_modifiers",
            "DROP TABLE IF EXISTS menu_items",
            "DROP TABLE IF EXISTS menu_categories",
            "DROP TABLE IF EXISTS audit_logs",
            "DROP TABLE IF EXISTS tenant_settings",
            "DROP TABLE IF EXISTS employee_users",
            "DROP TABLE IF EXISTS role_permissions",
            "DROP TABLE IF EXISTS roles",
        ]
    )
