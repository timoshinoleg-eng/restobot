# payments/worker.py
"""Payment processing worker for ЮKassa integration."""

import asyncio
import json
import logging
from datetime import datetime

import httpx
from yookassa import Configuration, Payment

from shared.config import get_settings
from shared.database import get_raw_pool

settings = get_settings()
logger = logging.getLogger(__name__)

# Configure ЮKassa
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


class PaymentWorker:
    """Async worker for processing payment events from YMQ."""
    
    def __init__(self):
        self.running = False
        self.client = httpx.AsyncClient(timeout=settings.YOOKASSA_TIMEOUT)
    
    async def process_payment(self, tenant_schema: str, order_id: int, return_url: str):
        """Create ЮKassa payment and return confirmation URL."""
        pool = await get_raw_pool()
        
        # Get order details
        order = await pool.fetchrow(f"""
            SELECT * FROM {tenant_schema}.orders WHERE id = $1
        """, order_id)
        
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order["payment_status"] != "pending":
            raise ValueError(f"Order {order_id} already processed")
        
        # Calculate amount (minus loyalty points)
        amount = float(order["amount"]) - float(order.get("loyalty_used", 0))
        
        # Create ЮKassa payment
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": f"Order #{order['order_number']}",
            "metadata": {
                "order_id": str(order_id),
                "tenant_schema": tenant_schema,
                "fiscal": {
                    "receipt": {
                        "customer": {
                            "email": order.get("user_email", ""),
                            "phone": order.get("phone", "")
                        },
                        "items": [
                            {
                                "description": item["name"],
                                "quantity": item["quantity"],
                                "amount": {
                                    "value": f"{item['price']:.2f}",
                                    "currency": "RUB"
                                },
                                "vat_code": 1  # 20% VAT
                            }
                            for item in json.loads(order["items_json"])
                        ]
                    }
                }
            }
        })
        
        # Save payment ID
        await pool.execute(f"""
            UPDATE {tenant_schema}.orders
            SET payment_id = $1, payment_provider = 'yookassa'
            WHERE id = $2
        """, payment.id, order_id)
        
        logger.info(f"Payment created: {payment.id} for order {order_id}")
        
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "status": payment.status
        }
    
    async def handle_webhook(self, tenant_schema: str, event: dict):
        """Handle ЮKassa webhook."""
        payment_id = event["object"]["id"]
        status = event["event"]  # payment.succeeded, payment.canceled, etc.
        
        pool = await get_raw_pool()
        
        # Find order by payment_id
        order = await pool.fetchrow(f"""
            SELECT id, order_number, user_id, loyalty_used
            FROM {tenant_schema}.orders
            WHERE payment_id = $1
        """, payment_id)
        
        if not order:
            logger.warning(f"Order not found for payment {payment_id}")
            return
        
        if status == "payment.succeeded":
            # Update order status
            await pool.execute(f"""
                UPDATE {tenant_schema}.orders
                SET payment_status = 'paid', paid_at = NOW(), status = 'confirmed'
                WHERE id = $1
            """, order["id"])
            
            # Accrue loyalty points (1% of order amount)
            await pool.execute(f"""
                UPDATE {tenant_schema}.users
                SET loyalty_points = loyalty_points + (
                    SELECT amount * 0.01 FROM {tenant_schema}.orders WHERE id = $1
                )
                WHERE id = $2
            """, order["id"], order["user_id"])
            
            logger.info(f"Order {order['id']} paid successfully")
            
        elif status == "payment.canceled":
            # Refund loyalty points
            if order["loyalty_used"] > 0:
                await pool.execute(f"""
                    UPDATE {tenant_schema}.users
                    SET loyalty_points = loyalty_points + $1
                    WHERE id = $2
                """, order["loyalty_used"], order["user_id"])
            
            await pool.execute(f"""
                UPDATE {tenant_schema}.orders
                SET payment_status = 'failed', status = 'cancelled'
                WHERE id = $1
            """, order["id"])
            
            logger.info(f"Order {order['id']} payment cancelled")
    
    async def run(self):
        """Main worker loop."""
        self.running = True
        logger.info("Payment worker started")
        
        while self.running:
            try:
                # Poll YMQ for payment events
                # ...
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        """Stop worker."""
        self.running = False
        await self.client.aclose()


def main():
    """Entry point."""
    worker = PaymentWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        asyncio.run(worker.stop())


if __name__ == "__main__":
    main()
