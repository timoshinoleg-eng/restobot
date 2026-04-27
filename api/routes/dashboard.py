# api/routes/dashboard.py
"""Dashboard analytics endpoints for owner/admin."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()


def _require_admin(request: Request) -> None:
    role = getattr(request.state, "user_role", "user")
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Admin or owner access required")


@router.get("/revenue")
async def revenue(
    request: Request,
    period: str = "day",
) -> dict[str, Any]:
    """Revenue aggregation by period."""
    _require_admin(request)
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()

    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=422, detail="period must be day, week or month")

    trunc = {"day": "day", "week": "week", "month": "month"}[period]
    rows = await pool.fetch(
        format_sql(
            f"""
            SELECT DATE_TRUNC('{trunc}', created_at) AS period,
                   COUNT(*) AS orders_count,
                   SUM(amount) AS total_revenue
            FROM {{}}.orders
            WHERE payment_status = 'paid'
            GROUP BY period
            ORDER BY period DESC
            LIMIT 30
            """,
            tenant_schema,
        )
    )
    return {
        "period": period,
        "data": [
            {
                "period": str(r["period"]),
                "orders_count": r["orders_count"],
                "total_revenue": float(r["total_revenue"]) if r["total_revenue"] else 0.0,
            }
            for r in rows
        ],
    }


@router.get("/top_dishes")
async def top_dishes(
    request: Request,
    limit: int = 10,
) -> dict[str, Any]:
    """Top selling dishes by quantity."""
    _require_admin(request)
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()

    rows = await pool.fetch(
        format_sql(
            """
            SELECT
                (item->>'menu_item_id')::int AS menu_item_id,
                SUM((item->>'quantity')::int) AS total_quantity,
                SUM((item->>'price')::float * (item->>'quantity')::int) AS total_revenue
            FROM {}.orders,
            LATERAL jsonb_array_elements(items_json::jsonb) AS item
            WHERE payment_status = 'paid'
            GROUP BY menu_item_id
            ORDER BY total_quantity DESC
            LIMIT $1
            """,
            tenant_schema,
        ),
        limit,
    )
    return {
        "limit": limit,
        "dishes": [
            {
                "menu_item_id": r["menu_item_id"],
                "total_quantity": r["total_quantity"],
                "total_revenue": float(r["total_revenue"]),
            }
            for r in rows
        ],
    }


@router.get("/table_turnover")
async def table_turnover(request: Request) -> dict[str, Any]:
    """Table turnover rate (reservations vs tables)."""
    _require_admin(request)
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()

    row = await pool.fetchrow(
        format_sql(
            """
            SELECT
                (SELECT COUNT(*) FROM {}.tables WHERE status = 'available') AS available_tables,
                (SELECT COUNT(*) FROM {}.reservations
                 WHERE status IN ('pending', 'confirmed')
                 AND start_time >= CURRENT_DATE
                 AND start_time < CURRENT_DATE + INTERVAL '1 day') AS today_reservations
            """,
            tenant_schema,
            tenant_schema,
        )
    )
    return {
        "available_tables": row["available_tables"] if row else 0,
        "today_reservations": row["today_reservations"] if row else 0,
    }
