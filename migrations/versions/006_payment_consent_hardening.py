"""Add consent, webhook ledger, and tenant VAT settings.

Revision ID: 006
Revises: 005
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_slugs() -> list[str]:
    bind = op.get_bind()
    rows = bind.execute(text("SELECT slug FROM shared.tenants WHERE status = 'active'")).fetchall()
    return [row[0] for row in rows]


def _schema_exists(schema_name: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM information_schema.schemata
                    WHERE schema_name = :schema
                )
                """
            ),
            {"schema": schema_name},
        ).scalar()
    )


def _upgrade_schema(schema_name: str) -> None:
    quoted = f'"{schema_name}"' if schema_name != "public" else ""
    prefix = f"{quoted}." if quoted else ""

    op.execute(
        f"""
        ALTER TABLE {prefix}restaurant_settings
        ADD COLUMN IF NOT EXISTS vat_code INT NOT NULL DEFAULT 1
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {prefix}user_consents (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES {prefix}users(id) ON DELETE SET NULL,
            telegram_user_id BIGINT,
            external_id VARCHAR(128),
            consent_version INT NOT NULL,
            consent_hash VARCHAR(64) NOT NULL,
            source VARCHAR(32) NOT NULL,
            agreed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_consents_external_active
        ON {prefix}user_consents (consent_version, source, external_id)
        WHERE external_id IS NOT NULL AND revoked_at IS NULL
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_user_consents_user_active
        ON {prefix}user_consents (user_id, consent_version)
        WHERE revoked_at IS NULL
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_user_consents_telegram_active
        ON {prefix}user_consents (telegram_user_id, consent_version)
        WHERE telegram_user_id IS NOT NULL AND revoked_at IS NULL
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {prefix}payment_webhook_events (
            id BIGSERIAL PRIMARY KEY,
            payment_id VARCHAR(128) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (payment_id, event_type)
        )
        """
    )


def upgrade() -> None:
    _upgrade_schema("public")
    for slug in _tenant_slugs():
        schema_name = f"tenant_{slug}"
        if _schema_exists(schema_name):
            _upgrade_schema(schema_name)


def _downgrade_schema(schema_name: str) -> None:
    quoted = f'"{schema_name}"' if schema_name != "public" else ""
    prefix = f"{quoted}." if quoted else ""
    op.execute(f"DROP TABLE IF EXISTS {prefix}payment_webhook_events CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {prefix}user_consents CASCADE")
    op.execute(f"ALTER TABLE {prefix}restaurant_settings DROP COLUMN IF EXISTS vat_code")


def downgrade() -> None:
    for slug in _tenant_slugs():
        schema_name = f"tenant_{slug}"
        if _schema_exists(schema_name):
            _downgrade_schema(schema_name)
    _downgrade_schema("public")
