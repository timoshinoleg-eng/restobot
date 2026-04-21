# api/routes/orders.py
"""Order management endpoints."""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shared.config import get_settings
from shared.database import get_raw_pool

router = APIRouter()
settings = get_settings()


class OrderItemRequest(BaseModel):
    menu_item_id: int
    quantity: int = 1
    modifiers: Optional[List[dict]] = None
    price: float


class OrderCreateRequest(BaseModel):
    user_id: int
    type: str  # delivery, pickup, dine_in, pre_order
    items: List[OrderItemRequest]
    address: Optional[str] = None
    phone: Optional[str] = None
    comment: Optional[str] = None
    scheduled_for: Optional[str] = None
    payment_method: Optional[str] = "cash"
    loyalty_points_to_use: Optional[float] = 0


class OrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    payment_status: str
    amount: float
    items: List[dict]
    created_at: str


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(request: Request, body: OrderCreateRequest):
    """Create a new order."""
    tenant_schema = request.state.tenant_schema
    pool = await get_raw_pool()
    
    # Validate minimum order amount
    settings_row = await pool.fetchrow(f"""
        SELECT min_order_amount FROM {tenant_schema}.restaurant_settings LIMIT 1
    """)
    
    total = sum(item.price * item.quantity for item in body.items)
    
    if settings_row and total < settings_row["min_order_amount"]:
        raise HTTPException(
            status_code=422,
            detail=f"Minimum order amount: {settings_row['min_order_amount']} ₽"
        )
    
    # Validate delivery address
    if body.type == "delivery" and not body.address:
        raise HTTPException(status_code=422, detail="Address required for delivery")
    
    # Apply loyalty points
    if body.loyalty_points_to_use > 0:
        user = await pool.fetchrow(f"""
            SELECT loyalty_points FROM {tenant_schema}.users WHERE id = $1
        """, body.user_id)
        
        if not user or user["loyalty_points"] < body.loyalty_points_to_use:
            raise HTTPException(status_code=422, detail="Insufficient loyalty points")
        
        # Max 50% discount
        if body.loyalty_points_to_use > total * 0.5:
            raise HTTPException(status_code=422, detail="Max 50% discount with loyalty points")
    
    # Generate order number
    order_number = f"R-{datetime.now().strftime('%y%m%d')}-{random.randint(1000, 9999)}"
    
    # Insert order
    order_id = await pool.fetchval(f"""
        INSERT INTO {tenant_schema}.orders (
            user_id, order_number, type, status, payment_status,
            payment_method, amount, delivery_fee, discount_amount, loyalty_used,
            items_json, address, phone, comment, scheduled_for
        ) VALUES ($1, $2, $3, 'new', 'pending', $4, $5, 0, $6, $7, $8, $9, $10, $11, $12)
        RETURNING id
    """,
        body.user_id, order_number, body.type, body.payment_method,
        total, body.loyalty_points_to_use, body.loyalty_points_to_use,
        [item.model_dump() for item in body.items],
        body.address, body.phone, body.comment, body.scheduled_for
    )
    
    # Deduct loyalty points
    if body.loyalty_points_to_use > 0:
        await pool.execute(f"""
            UPDATE {tenant_schema}.users
            SET loyalty_points = loyalty_points - $1
            WHERE id = $2
        """, body.loyalty_points_to_use, body.user_id)
        
        # Log transaction
        await pool.execute(f"""
            INSERT INTO {tenant_schema}.loyalty_transactions
            (user_id, order_id, type, points, balance_after, description)
            VALUES ($1, $2, 'spend', $3, 
                (SELECT loyalty_points FROM {tenant_schema}.users WHERE id = $1),
                'Order #{4}'
            )
        """, body.user_id, order_id, -body.loyalty_points_to_use, order_number)
    
    # Enqueue notification
    # ...
    
    return {
        "id": order_id,
        "order_number": order_number,
        "status": "new",
        "payment_status": "pending",
        "amount": float(total),
        "items": [item.model_dump() for item in body.items],
        "created_at": datetime.now().isoformat(),
    }


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(request: Request, order_id: int):
    """Get order by ID."""
    tenant_schema = request.state.tenant_schema
    pool = await get_raw_pool()
    
    row = await pool.fetchrow(f"""
        SELECT * FROM {tenant_schema}.orders WHERE id = $1
    """, order_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return dict(row)


@router.get("/orders")
async def list_orders(request: Request, user_id: Optional[int] = None, status: Optional[str] = None):
    """List orders with filters."""
    tenant_schema = request.state.tenant_schema
    pool = await get_raw_pool()
    
    query = f"SELECT * FROM {tenant_schema}.orders WHERE 1=1"
    params = []
    
    if user_id:
        params.append(user_id)
        query += f" AND user_id = ${len(params)}"
    
    if status:
        params.append(status)
        query += f" AND status = ${len(params)}"
    
    query += " ORDER BY created_at DESC LIMIT 50"
    
    rows = await pool.fetch(query, *params)
    return [dict(row) for row in rows]
