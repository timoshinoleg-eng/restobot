"""Dashboard analytics endpoints for the admin API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.middleware import get_db
from backend.auth.permissions import require_permission
from backend.schemas.dashboard import DashboardSummaryOut, TopDishOut
from shared.redis_client import get_redis

router = APIRouter(prefix="/admin/v1/dashboard", tags=["dashboard"])


async def _get_dashboard_summary(
    db: AsyncSession,
    tenant_id: str,
    date_from: datetime,
    date_to: datetime,
) -> DashboardSummaryOut:
    cache_key = (
        f"dashboard:summary:{tenant_id}:{date_from.astimezone(timezone.utc).isoformat()}:"
        f"{date_to.astimezone(timezone.utc).isoformat()}"
    )
    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        payload = json.loads(cached)
        return DashboardSummaryOut(**payload)

    stmt = text(
        """
        WITH paid_orders AS (
            SELECT id, COALESCE(total_amount, amount, 0) AS total_amount
            FROM orders
            WHERE payment_status = 'paid'
              AND created_at >= :date_from
              AND created_at < :date_to
        ),
        order_totals AS (
            SELECT
                COALESCE(SUM(total_amount), 0) AS revenue,
                COUNT(*) AS orders_count,
                COALESCE(AVG(total_amount), 0) AS avg_check
            FROM paid_orders
        ),
        ranked_dishes AS (
            SELECT
                oi.menu_item_id AS dish_id,
                oi.item_name_snapshot AS dish_name,
                SUM(oi.quantity) AS qty,
                SUM(oi.line_total) AS revenue,
                ROW_NUMBER() OVER (ORDER BY SUM(oi.line_total) DESC, SUM(oi.quantity) DESC) AS rn
            FROM order_items oi
            INNER JOIN paid_orders po ON po.id = oi.order_id
            GROUP BY oi.menu_item_id, oi.item_name_snapshot
        )
        SELECT json_build_object(
            'revenue', ot.revenue,
            'orders_count', ot.orders_count,
            'avg_check', ot.avg_check,
            'top_dishes', COALESCE((
                SELECT json_agg(
                    json_build_object(
                        'dish_id', rd.dish_id,
                        'name', rd.dish_name,
                        'qty', rd.qty,
                        'revenue', rd.revenue
                    ) ORDER BY rd.rn
                )
                FROM ranked_dishes rd
                WHERE rd.rn <= 5
            ), '[]'::json)
        ) AS payload
        FROM order_totals ot
        """
    )
    raw_payload: dict[str, Any] = (
        await db.execute(stmt, {"date_from": date_from, "date_to": date_to})
    ).scalar_one()
    await redis.setex(cache_key, 30, json.dumps(raw_payload, default=str))
    top_dishes = [TopDishOut(**row) for row in raw_payload.get("top_dishes", [])]
    return DashboardSummaryOut(
        revenue=Decimal(str(raw_payload["revenue"])),
        orders_count=int(raw_payload["orders_count"]),
        avg_check=Decimal(str(raw_payload["avg_check"])),
        top_dishes=top_dishes,
    )


@router.get(
    "/summary",
    response_model=DashboardSummaryOut,
    dependencies=[Depends(require_permission("dashboard.read"))],
)
async def get_summary(
    request: Any,
    db: AsyncSession = Depends(get_db),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> DashboardSummaryOut:
    """Return revenue, order count and top dishes for the selected period."""

    effective_to = date_to or datetime.now(timezone.utc)
    effective_from = date_from or (effective_to - timedelta(days=1))
    return await _get_dashboard_summary(
        db,
        tenant_id=request.state.tenant_id,
        date_from=effective_from,
        date_to=effective_to,
    )
