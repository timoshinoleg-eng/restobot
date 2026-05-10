# api/routes/payments.py
"""Payment endpoints."""

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from payments.worker import PaymentWorker
from shared.auth_dependencies import bind_tenant_context, require_authenticated_user
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
worker = PaymentWorker()


@router.post("/orders/{order_id}/payment")
async def create_yookassa_payment(tenant: str, order_id: int, request: Request) -> dict[str, Any]:
    """Create a redirect payment for an existing online order."""
    if not settings.YOOKASSA_ENABLED:
        raise HTTPException(status_code=503, detail="Online payments are currently disabled")
    bind_tenant_context(request, tenant)
    require_authenticated_user(request)

    tenant_schema = request.state.tenant_schema
    pool = await get_raw_pool()
    order = await pool.fetchrow(
        format_sql(
            """
            SELECT id, user_id, payment_method, payment_status, payment_id
            FROM {}.orders
            WHERE id = $1
            """,
            tenant_schema,
        ),
        order_id,
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    user_role = getattr(request.state, "user_role", None)
    request_user_id = getattr(request.state, "user_id", None)
    if user_role not in {"admin", "owner"} and request_user_id != int(order["user_id"]):
        raise HTTPException(status_code=403, detail="User mismatch")
    if order["payment_method"] != "online":
        raise HTTPException(status_code=422, detail="Order is not configured for online payment")
    if order["payment_status"] == "paid":
        raise HTTPException(status_code=422, detail="Order is already paid")
    if order["payment_id"]:
        raise HTTPException(status_code=409, detail="Payment has already been initiated")

    return await worker.process_payment(
        tenant_schema=tenant_schema,
        order_id=order_id,
        return_url=settings.YOOKASSA_RETURN_URL,
    )


@router.post("/webhook/yookassa")
async def yookassa_webhook(tenant: str, request: Request) -> dict[str, str]:
    """Handle ЮKassa webhook with mandatory HMAC signature verification."""
    if not settings.YOOKASSA_ENABLED:
        raise HTTPException(status_code=503, detail="Online payments are currently disabled")
    bind_tenant_context(request, tenant)
    body = await request.body()
    secret = settings.YOOKASSA_WEBHOOK_SECRET
    if not secret:
        logger.error("YOOKASSA_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=500, detail="Webhook secret is not configured")
    sig = request.headers.get("X-Webhook-Signature", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="Invalid signature")

    event: dict[str, Any] = json.loads(body)
    tenant_schema = request.state.tenant_schema
    metadata = event.get("object", {}).get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("tenant_schema"):
        if metadata["tenant_schema"] != tenant_schema:
            raise HTTPException(status_code=400, detail="Webhook tenant mismatch")

    await worker.handle_webhook(tenant_schema, event)
    return {"status": "ok"}
