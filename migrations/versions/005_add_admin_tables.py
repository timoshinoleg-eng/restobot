"""Add audit_log, loyalty_settings, working_hours, onboarding_state tables.

Revision ID: 005
Revises: 004
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Fetch active tenants early (used in multiple loops)
    tenant_slugs = bind.execute(text("""
        SELECT slug FROM shared.tenants WHERE status = 'active'
    """)).fetchall()

    # Add missing columns to users (public + tenant schemas)
    op.execute("""
        ALTER TABLE restaurant_settings
        ADD COLUMN IF NOT EXISTS delivery_radius NUMERIC(12,2) DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE restaurant_settings
        ADD COLUMN IF NOT EXISTS setup_token VARCHAR(64)
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(64)
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
    """)

    for (slug,) in tenant_slugs:
        schema_name = f"tenant_{slug}"
        schema_exists = bind.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = :schema
            )
        """), {"schema": schema_name}).scalar()
        if schema_exists:
            bind.execute(text(f"""
                ALTER TABLE "{schema_name}".restaurant_settings
                ADD COLUMN IF NOT EXISTS delivery_radius NUMERIC(12,2) DEFAULT 0
            """))
            bind.execute(text(f"""
                ALTER TABLE "{schema_name}".restaurant_settings
                ADD COLUMN IF NOT EXISTS setup_token VARCHAR(64)
            """))
            bind.execute(text(f"""
                ALTER TABLE "{schema_name}".users
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
            """))
            bind.execute(text(f"""
                ALTER TABLE "{schema_name}".users
                ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(64)
            """))
            bind.execute(text(f"""
                ALTER TABLE "{schema_name}".users
                ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
            """))

    # Create tables in public schema (legacy compatibility)
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
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
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created
        ON audit_log (tenant_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_user
        ON audit_log (user_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_table_action
        ON audit_log (table_name, action)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_settings (
            id BIGSERIAL PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL UNIQUE,
            bonus_percent NUMERIC(5,2) NOT NULL DEFAULT 5.0,
            max_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 30.0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS working_hours (
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
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_state (
            id BIGSERIAL PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL UNIQUE,
            current_step VARCHAR(32) NOT NULL DEFAULT 'welcome',
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Propagate new tables to existing tenant schemas
    for (slug,) in tenant_slugs:
        schema_name = f"tenant_{slug}"
        schema_exists = bind.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = :schema
            )
        """), {"schema": schema_name}).scalar()

        if not schema_exists:
            continue

        bind.execute(text(f"""
            CREATE TABLE IF NOT EXISTS "{schema_name}".audit_log (
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
        """))
        bind.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created
            ON "{schema_name}".audit_log (tenant_id, created_at DESC)
        """))
        bind.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_audit_log_user
            ON "{schema_name}".audit_log (user_id)
        """))
        bind.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_audit_log_table_action
            ON "{schema_name}".audit_log (table_name, action)
        """))

        bind.execute(text(f"""
            CREATE TABLE IF NOT EXISTS "{schema_name}".loyalty_settings (
                id BIGSERIAL PRIMARY KEY,
                tenant_id VARCHAR(64) NOT NULL UNIQUE,
                bonus_percent NUMERIC(5,2) NOT NULL DEFAULT 5.0,
                max_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 30.0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

        bind.execute(text(f"""
            CREATE TABLE IF NOT EXISTS "{schema_name}".working_hours (
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
        """))

        bind.execute(text(f"""
            CREATE TABLE IF NOT EXISTS "{schema_name}".onboarding_state (
                id BIGSERIAL PRIMARY KEY,
                tenant_id VARCHAR(64) NOT NULL UNIQUE,
                current_step VARCHAR(32) NOT NULL DEFAULT 'welcome',
                completed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

        # Seed default working hours (Mon-Sun 10:00-22:00)
        for dow in range(7):
            bind.execute(text(f"""
                INSERT INTO "{schema_name}".working_hours
                (tenant_id, day_of_week, open_time, close_time, is_closed)
                VALUES (:tenant_id, :dow, '10:00', '22:00', FALSE)
                ON CONFLICT (tenant_id, day_of_week) DO NOTHING
            """), {"tenant_id": slug, "dow": dow})

        # Seed onboarding state
        bind.execute(text(f"""
            INSERT INTO "{schema_name}".onboarding_state (tenant_id, current_step)
            VALUES (:tenant_id, 'welcome')
            ON CONFLICT (tenant_id) DO NOTHING
        """), {"tenant_id": slug})


def downgrade() -> None:
    bind = op.get_bind()

    tenant_slugs = bind.execute(text("""
        SELECT slug FROM shared.tenants WHERE status = 'active'
    """)).fetchall()

    for (slug,) in tenant_slugs:
        schema_name = f"tenant_{slug}"
        schema_exists = bind.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = :schema
            )
        """), {"schema": schema_name}).scalar()
        if schema_exists:
            bind.execute(text(f'ALTER TABLE "{schema_name}".users DROP COLUMN IF EXISTS password_hash'))
            bind.execute(text(f'ALTER TABLE "{schema_name}".users DROP COLUMN IF EXISTS telegram_id'))
            bind.execute(text(f'ALTER TABLE "{schema_name}".users DROP COLUMN IF EXISTS is_active'))
            bind.execute(text(f'ALTER TABLE "{schema_name}".restaurant_settings DROP COLUMN IF EXISTS setup_token'))
            bind.execute(text(f'ALTER TABLE "{schema_name}".restaurant_settings DROP COLUMN IF EXISTS delivery_radius'))
            bind.execute(text(f'DROP TABLE IF EXISTS "{schema_name}".onboarding_state CASCADE'))
            bind.execute(text(f'DROP TABLE IF EXISTS "{schema_name}".working_hours CASCADE'))
            bind.execute(text(f'DROP TABLE IF EXISTS "{schema_name}".loyalty_settings CASCADE'))
            bind.execute(text(f'DROP TABLE IF EXISTS "{schema_name}".audit_log CASCADE'))

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_hash")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS telegram_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active")
    op.execute("ALTER TABLE restaurant_settings DROP COLUMN IF EXISTS setup_token")
    op.execute("ALTER TABLE restaurant_settings DROP COLUMN IF EXISTS delivery_radius")
    op.execute("DROP TABLE IF EXISTS onboarding_state CASCADE")
    op.execute("DROP TABLE IF EXISTS working_hours CASCADE")
    op.execute("DROP TABLE IF EXISTS loyalty_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
