"""Create shared and public baseline schema for MVP migrations.

Revision ID: 000
Revises:
Create Date: 2026-04-28 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS shared")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS shared.tenants (
            id BIGSERIAL PRIMARY KEY,
            slug VARCHAR(64) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            inn VARCHAR(12),
            ogrn VARCHAR(15),
            legal_address VARCHAR(500),
            actual_address VARCHAR(500),
            phone VARCHAR(20),
            email VARCHAR(255),
            timezone VARCHAR(50) NOT NULL DEFAULT 'Europe/Moscow',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            dpo_name VARCHAR(255),
            dpo_email VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS shared.plans (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            price_monthly NUMERIC(12,2) NOT NULL,
            max_menu_items INT NOT NULL DEFAULT 100,
            max_staff INT NOT NULL DEFAULT 10,
            max_orders_day INT NOT NULL DEFAULT 500,
            has_ai BOOLEAN NOT NULL DEFAULT FALSE,
            has_delivery BOOLEAN NOT NULL DEFAULT FALSE,
            has_loyalty BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS shared.subscriptions (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL REFERENCES shared.tenants(id) ON DELETE CASCADE,
            plan_id BIGINT NOT NULL REFERENCES shared.plans(id),
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            auto_renew BOOLEAN NOT NULL DEFAULT TRUE,
            payment_method VARCHAR(50),
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            external_id VARCHAR(128) UNIQUE,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            email VARCHAR(255),
            loyalty_points NUMERIC(12,2) NOT NULL DEFAULT 0,
            role VARCHAR(20) NOT NULL DEFAULT 'user',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_categories (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            emoji VARCHAR(16),
            sort_order INT NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id BIGSERIAL PRIMARY KEY,
            category_id BIGINT REFERENCES menu_categories(id) ON DELETE SET NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            price NUMERIC(12,2) NOT NULL,
            image_url TEXT,
            is_available BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurant_settings (
            id BIGSERIAL PRIMARY KEY,
            restaurant_name VARCHAR(255) NOT NULL,
            min_order_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            currency VARCHAR(8) NOT NULL DEFAULT 'RUB',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
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
            paid_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS loyalty_transactions (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id),
            order_id BIGINT REFERENCES orders(id) ON DELETE SET NULL,
            type VARCHAR(20) NOT NULL,
            points NUMERIC(12,2) NOT NULL,
            balance_after NUMERIC(12,2) NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_dlq (
            id BIGSERIAL PRIMARY KEY,
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payment_dlq")
    op.execute("DROP TABLE IF EXISTS loyalty_transactions")
    op.execute("DROP TABLE IF EXISTS orders")
    op.execute("DROP TABLE IF EXISTS restaurant_settings")
    op.execute("DROP TABLE IF EXISTS menu_items")
    op.execute("DROP TABLE IF EXISTS menu_categories")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS shared.subscriptions")
    op.execute("DROP TABLE IF EXISTS shared.plans")
    op.execute("DROP TABLE IF EXISTS shared.tenants")
