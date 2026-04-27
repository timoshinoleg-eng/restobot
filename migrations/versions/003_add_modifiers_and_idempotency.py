"""Add modifier tables and idempotency key to orders.

Revision ID: 003
Revises: 002
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS menu_item_modifiers (
            id SERIAL PRIMARY KEY,
            menu_item_id INT NOT NULL,
            name VARCHAR(255) NOT NULL,
            required BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS modifier_options (
            id SERIAL PRIMARY KEY,
            modifier_id INT NOT NULL REFERENCES menu_item_modifiers(id),
            name VARCHAR(255) NOT NULL,
            price NUMERIC(12,2) NOT NULL DEFAULT 0.0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64) UNIQUE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS idempotency_key")
    op.execute("DROP TABLE IF EXISTS modifier_options")
    op.execute("DROP TABLE IF EXISTS menu_item_modifiers")
