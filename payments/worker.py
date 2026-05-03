# payments/worker.py
"""Payment processing worker for ЮKassa integration."""

import asyncio
import json
import logging
import uuid
from typing import Any

import httpx
from yookassa import Configuration, Payment

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

settings = get_settings()
logger = logging.getLogger(__name__)

# Configure ЮKassa
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


class PaymentWorker:
    """Async worker for processing payment events with idempotency and DLQ."""

    def __init__(self) -> None:
        self.running = False
        self.client = httpx.AsyncClient(timeout=settings.YOOKASSA_TIMEOUT)

    async def process_payment(
        self, tenant_schema: str, order_id: int, return_url: str
    ) -> dict[str, Any]:
        """Create ЮKassa payment with idempotency and return confirmation URL."""
        pool = await get_raw_pool()
        idempotency_key = str(uuid.uuid4())

        async with pool.acquire() as conn:
            async with conn.transaction():
                order = await conn.fetchrow(
                    format_sql("SELECT * FROM {}.orders WHERE id = $1", tenant_schema),
                    order_id,
                )

                if not order:
                    raise ValueError(f"Order {order_id} not found")

                if order["payment_status"] != "pending":
                    raise ValueError(f"Order {order_id} already processed")

                amount = float(order["amount"]) - float(order.get("loyalty_used", 0))
                if amount <= 0:
                    raise ValueError(f"Invalid payment amount for order {order_id}")

                items_json: list[dict[str, Any]] = json.loads(order["items_json"])
                item_ids = [
                    int(item["menu_item_id"])
                    for item in items_json
                    if isinstance(item.get("menu_item_id"), int)
                ]
                item_name_map: dict[int, str] = {}
                if item_ids:
                    menu_rows = await conn.fetch(
                        format_sql(
                            "SELECT id, name FROM {}.menu_items WHERE id = ANY($1::bigint[])",
                            tenant_schema,
                        ),
                        item_ids,
                    )
                    item_name_map = {int(row["id"]): str(row["name"]) for row in menu_rows}

                receipt_customer = {
                    key: value
                    for key, value in {
                        "email": order.get("user_email", ""),
                        "phone": order.get("phone", ""),
                    }.items()
                    if value
                }
                receipt_items = [
                    {
                        "description": item_name_map.get(
                            int(item["menu_item_id"]),
                            f"Позиция #{item['menu_item_id']}",
                        )[:128],
                        "quantity": item["quantity"],
                        "amount": {
                            "value": f"{float(item['price']):.2f}",
                            "currency": "RUB",
                        },
                        "payment_mode": "full_payment",
                        "payment_subject": "commodity",
                        "vat_code": 1,  # 20% VAT
                    }
                    for item in items_json
                ]

                payment_payload: dict[str, Any] = {
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": "RUB",
                    },
                    "confirmation": {
                        "type": "redirect",
                        "return_url": return_url,
                    },
                    "capture": True,
                    "description": f"Order #{order['order_number']}",
                    "receipt": {
                        "customer": receipt_customer,
                        "items": receipt_items,
                    },
                    "metadata": {
                        "order_id": str(order_id),
                        "tenant_schema": tenant_schema,
                        "idempotency_key": idempotency_key,
                    },
                }

                # Create ЮKassa payment (synchronous SDK call wrapped)
                payment = await asyncio.to_thread(Payment.create, payment_payload, idempotency_key)

                await conn.execute(
                    format_sql(
                        """
                        UPDATE {}.orders
                        SET payment_id = $1, payment_provider = 'yookassa',
                            payment_idempotency_key = $2
                        WHERE id = $3
                        """,
                        tenant_schema,
                    ),
                    payment.id,
                    idempotency_key,
                    order_id,
                )

        logger.info(
            "Payment created: %s for order %s (idempotency=%s)",
            payment.id,
            order_id,
            idempotency_key,
        )

        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "status": payment.status,
        }

    async def handle_webhook(self, tenant_schema: str, event: dict[str, Any]) -> None:
        """Handle ЮKassa webhook with idempotency guard."""
        payment_id = event["object"]["id"]
        event_type = event["event"]  # payment.succeeded, payment.canceled, etc.
        pool = await get_raw_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():
                order = await conn.fetchrow(
                    format_sql(
                        """
                        SELECT id, order_number, user_id, loyalty_used, payment_status
                        FROM {}.orders
                        WHERE payment_id = $1
                        """,
                        tenant_schema,
                    ),
                    payment_id,
                )

                if not order:
                    logger.warning("Order not found for payment %s", payment_id)
                    return

                # Idempotency guard
                if order["payment_status"] == "paid" and event_type == "payment.succeeded":
                    logger.info("Duplicate webhook ignored for order %s", order["id"])
                    return

                if event_type == "payment.succeeded":
                    await conn.execute(
                        format_sql(
                            """
                            UPDATE {}.orders
                            SET payment_status = 'paid', paid_at = NOW(), status = 'confirmed'
                            WHERE id = $1
                            """,
                            tenant_schema,
                        ),
                        order["id"],
                    )

                    # Accrue loyalty points (1% of order amount)
                    await conn.execute(
                        format_sql(
                            """
                            UPDATE {}.users
                            SET loyalty_points = loyalty_points + (
                                SELECT amount * 0.01
                                FROM {}.orders
                                WHERE id = $1
                            )
                            WHERE id = $2
                            """,
                            tenant_schema,
                            tenant_schema,
                        ),
                        order["id"],
                        order["user_id"],
                    )

                    logger.info("Order %s paid successfully", order["id"])

                elif event_type == "payment.canceled":
                    if float(order.get("loyalty_used", 0)) > 0:
                        await conn.execute(
                            format_sql(
                                """
                                UPDATE {}.users
                                SET loyalty_points = loyalty_points + $1
                                WHERE id = $2
                                """,
                                tenant_schema,
                            ),
                            float(order["loyalty_used"]),
                            order["user_id"],
                        )

                    await conn.execute(
                        format_sql(
                            """
                            UPDATE {}.orders
                            SET payment_status = 'failed', status = 'cancelled'
                            WHERE id = $1
                            """,
                            tenant_schema,
                        ),
                        order["id"],
                    )

                    logger.info("Order %s payment cancelled", order["id"])

    async def poll_payment_status(self, tenant_schema: str, payment_id: str, order_id: int) -> bool:
        """Poll ЮKassa for payment status as webhook fallback."""
        for _ in range(12):  # 12 attempts * 5s = 60s
            try:
                payment = await asyncio.to_thread(Payment.find_one, payment_id)
                if payment.status == "succeeded":
                    await self.handle_webhook(
                        tenant_schema,
                        {
                            "event": "payment.succeeded",
                            "object": {"id": payment_id},
                        },
                    )
                    return True
                if payment.status == "canceled":
                    await self.handle_webhook(
                        tenant_schema,
                        {
                            "event": "payment.canceled",
                            "object": {"id": payment_id},
                        },
                    )
                    return True
            except Exception as exc:
                logger.warning("Payment polling error for %s: %s", payment_id, exc)
            await asyncio.sleep(5)
        return False

    async def enqueue_dlq(self, tenant_schema: str, event: dict[str, Any]) -> None:
        """Enqueue failed payment event to dead-letter queue table."""
        pool = await get_raw_pool()
        try:
            await pool.execute(
                format_sql(
                    """
                    INSERT INTO {}.payment_dlq
                    (event_type, payload, created_at)
                    VALUES ($1, $2, NOW())
                    """,
                    tenant_schema,
                ),
                event.get("event", "unknown"),
                json.dumps(event),
            )
        except Exception as exc:
            logger.error("Failed to enqueue DLQ: %s", exc)

    async def run(self) -> None:
        """Main worker loop with graceful error handling."""
        self.running = True
        logger.info("Payment worker started")

        while self.running:
            try:
                # Poll YMQ for payment events (placeholder)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("Payment worker cancelled")
                break
            except Exception as exc:
                logger.error("Worker error: %s", exc)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop worker and close HTTP client."""
        self.running = False
        await self.client.aclose()
        logger.info("Payment worker stopped")


async def send_order_status_update(order_id: int, status: str) -> None:
    """Stub for sending order status update notifications."""
    logger.info("Order %s status updated to %s", order_id, status)


def main() -> None:
    """Entry point with graceful shutdown."""
    worker = PaymentWorker()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(worker.run())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
    finally:
        loop.run_until_complete(worker.stop())
        loop.close()


if __name__ == "__main__":
    main()
