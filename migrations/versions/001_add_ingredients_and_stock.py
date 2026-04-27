"""Add ingredients, recipe and stock_movements tables.

Revision ID: 001
Revises:
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            unit VARCHAR(20) DEFAULT 'г',
            current_stock NUMERIC(12,2) DEFAULT 0.0,
            reserved_stock NUMERIC(12,2) DEFAULT 0.0,
            min_stock NUMERIC(12,2) DEFAULT 0.0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS recipe (
            id SERIAL PRIMARY KEY,
            menu_item_id INT NOT NULL,
            ingredient_id INT NOT NULL REFERENCES ingredients(id),
            grams_needed NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            id SERIAL PRIMARY KEY,
            ingredient_id INT NOT NULL REFERENCES ingredients(id),
            type VARCHAR(20) NOT NULL CHECK (
                type IN ('incoming', 'outgoing', 'reserve', 'adjustment')
            ),
            quantity NUMERIC(12,2) NOT NULL,
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stock_movements")
    op.execute("DROP TABLE IF EXISTS recipe")
    op.execute("DROP TABLE IF EXISTS ingredients")
