# api/routes/payments.py
"""Payment endpoints."""

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from payments.worker import PaymentWorker
from shared.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
worker = PaymentWorker()


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request) -> dict[str, str]:
    """Handle ЮKassa webhook with optional HMAC signature verification."""
    body = await request.body()
    secret = settings.YOOKASSA_WEBHOOK_SECRET
    if secret:
        sig = request.headers.get("X-Webhook-Signature", "")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=400, detail="Invalid signature")

    event: dict[str, Any] = json.loads(body)
    tenant_schema = "tenant_default"
    metadata = event.get("object", {}).get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("tenant_schema"):
        tenant_schema = metadata["tenant_schema"]

    await worker.handle_webhook(tenant_schema, event)
    return {"status": "ok"}
