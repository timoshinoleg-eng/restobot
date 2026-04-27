"""Add tables and reservations tables.

Revision ID: 002
Revises: 001
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            id SERIAL PRIMARY KEY,
            number VARCHAR(10) NOT NULL,
            capacity INT NOT NULL DEFAULT 4,
            location VARCHAR(100),
            status VARCHAR(20) DEFAULT 'available',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id SERIAL PRIMARY KEY,
            table_id INT NOT NULL REFERENCES tables(id),
            user_id INT NOT NULL,
            guest_name VARCHAR(255) NOT NULL,
            guest_phone VARCHAR(20) NOT NULL,
            start_time TIMESTAMPTZ NOT NULL,
            end_time TIMESTAMPTZ NOT NULL,
            guests_count INT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_reservations_table_time
        ON reservations (table_id, start_time, end_time)
        WHERE status IN ('pending', 'confirmed')
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reservations")
    op.execute("DROP TABLE IF EXISTS tables")
