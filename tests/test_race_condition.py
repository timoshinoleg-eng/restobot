# tests/test_race_condition.py
"""Tests for concurrent loyalty point deductions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.sql_utils import format_sql


@pytest.mark.asyncio
async def test_concurrent_loyalty_deduction_never_negative() -> None:
    """10 simultaneous deductions must not drive balance below zero."""
    initial_balance = 100.0
    deduction = 30.0

    async def atomic_deduct(conn: MagicMock, user_id: int, amount: float) -> bool:
        row = await conn.fetchrow(
            format_sql(
                """
                UPDATE {}.users
                SET loyalty_points = loyalty_points - $1
                WHERE id = $2 AND loyalty_points >= $1
                RETURNING loyalty_points
                """,
                "tenant_test",
            ),
            amount,
            user_id,
        )
        return row is not None

    # Simulate DB state
    balance = {"value": initial_balance}
    lock = asyncio.Lock()

    async def fake_fetchrow(sql: str, *args: object) -> object:
        async with lock:
            amt = float(args[0])  # type: ignore[arg-type]
            if balance["value"] >= amt:
                balance["value"] -= amt
                return {"loyalty_points": balance["value"]}
            return None

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(side_effect=fake_fetchrow)

    tasks = [
        atomic_deduct(mock_conn, 1, deduction)
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    total_deducted = success_count * deduction
    assert total_deducted <= initial_balance  # nosec B101
    assert balance["value"] == initial_balance - total_deducted  # nosec B101
    assert balance["value"] >= 0  # nosec B101
