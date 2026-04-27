# api/routes/ingredients.py
"""Ingredient and stock management endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()


class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    unit: str = Field(default="г", max_length=20)
    current_stock: float = Field(default=0.0, ge=0)
    reserved_stock: float = Field(default=0.0, ge=0)
    min_stock: float = Field(default=0.0, ge=0)


class StockMovementCreate(BaseModel):
    ingredient_id: int = Field(..., ge=1)
    type: str = Field(..., pattern=r"^(incoming|outgoing|adjustment)$")
    quantity: float = Field(..., gt=0)
    comment: Optional[str] = None


@router.get("/ingredients")
async def list_ingredients(request: Request) -> list[dict[str, Any]]:
    """List all ingredients with stock levels."""
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()
    rows = await pool.fetch(
        format_sql("SELECT * FROM {}.ingredients ORDER BY name", tenant_schema)
    )
    return [dict(r) for r in rows]


@router.post("/ingredients", status_code=201)
async def create_ingredient(
    request: Request, body: IngredientCreate
) -> dict[str, Any]:
    """Create a new ingredient."""
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()
    row = await pool.fetchrow(
        format_sql(
            """
            INSERT INTO {}.ingredients (name, unit, current_stock, reserved_stock, min_stock)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            tenant_schema,
        ),
        body.name,
        body.unit,
        body.current_stock,
        body.reserved_stock,
        body.min_stock,
    )
    return dict(row)


@router.post("/stock/incoming", status_code=201)
async def stock_incoming(
    request: Request, body: StockMovementCreate
) -> dict[str, Any]:
    """Record incoming stock and update ingredient balance."""
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                format_sql(
                    """
                    UPDATE {}.ingredients
                    SET current_stock = current_stock + $1
                    WHERE id = $2
                    RETURNING current_stock
                    """,
                    tenant_schema,
                ),
                body.quantity,
                body.ingredient_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Ingredient not found")

            await conn.execute(
                format_sql(
                    """
                    INSERT INTO {}.stock_movements
                    (ingredient_id, type, quantity, comment, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    """,
                    tenant_schema,
                ),
                body.ingredient_id,
                body.type,
                body.quantity,
                body.comment,
            )

    return {
        "ingredient_id": body.ingredient_id,
        "new_stock": float(row["current_stock"]),
        "movement_type": body.type,
    }
