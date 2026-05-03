# api/routes/ingredients.py
"""Ingredient and stock management endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.audit_utils import log_audit
from shared.auth_dependencies import require_admin_user
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


class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    unit: Optional[str] = Field(default=None, max_length=20)
    current_stock: Optional[float] = Field(default=None, ge=0)
    reserved_stock: Optional[float] = Field(default=None, ge=0)
    min_stock: Optional[float] = Field(default=None, ge=0)


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


@router.get("/ingredients/{ingredient_id}")
async def get_ingredient(request: Request, ingredient_id: int) -> dict[str, Any]:
    """Get ingredient details."""
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()
    row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.ingredients WHERE id = $1", tenant_schema),
        ingredient_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return dict(row)


@router.post("/ingredients", status_code=201)
async def create_ingredient(
    request: Request, body: IngredientCreate
) -> dict[str, Any]:
    """Create a new ingredient. Admin/owner only."""
    require_admin_user(request)
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
    assert row is not None
    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="CREATE",
        table_name="ingredients",
        record_id=int(row["id"]),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.put("/ingredients/{ingredient_id}")
async def update_ingredient(
    request: Request, ingredient_id: int, body: IngredientUpdate
) -> dict[str, Any]:
    """Update an ingredient. Admin/owner only."""
    require_admin_user(request)
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.ingredients WHERE id = $1", tenant_schema),
        ingredient_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    fields: list[str] = []
    params: list[Any] = []

    if body.name is not None:
        fields.append("name = $" + str(len(params) + 1))
        params.append(body.name)
    if body.unit is not None:
        fields.append("unit = $" + str(len(params) + 1))
        params.append(body.unit)
    if body.current_stock is not None:
        fields.append("current_stock = $" + str(len(params) + 1))
        params.append(body.current_stock)
    if body.reserved_stock is not None:
        fields.append("reserved_stock = $" + str(len(params) + 1))
        params.append(body.reserved_stock)
    if body.min_stock is not None:
        fields.append("min_stock = $" + str(len(params) + 1))
        params.append(body.min_stock)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    query = format_sql(
        f"""
        UPDATE {{}}.ingredients
        SET {', '.join(fields)}
        WHERE id = ${len(params) + 1}
        RETURNING *
        """,
        tenant_schema,
    )
    params.append(ingredient_id)

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="ingredients",
        record_id=ingredient_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.delete("/ingredients/{ingredient_id}")
async def delete_ingredient(request: Request, ingredient_id: int) -> dict[str, Any]:
    """Delete an ingredient if not used in recipes. Admin/owner only."""
    require_admin_user(request)
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            recipes = await conn.fetchval(
                format_sql(
                    "SELECT COUNT(*) FROM {}.recipes WHERE ingredient_id = $1",
                    tenant_schema,
                ),
                ingredient_id,
            )
            if recipes and int(recipes) > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Ingredient is used in recipes. Remove recipes first.",
                )

            old_row = await conn.fetchrow(
                format_sql("SELECT * FROM {}.ingredients WHERE id = $1", tenant_schema),
                ingredient_id,
            )
            if not old_row:
                raise HTTPException(status_code=404, detail="Ingredient not found")

            await conn.execute(
                format_sql("DELETE FROM {}.ingredients WHERE id = $1", tenant_schema),
                ingredient_id,
            )

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="DELETE",
        table_name="ingredients",
        record_id=ingredient_id,
        old_values=dict(old_row),
        ip_address=request.client.host if request.client else None,
    )
    return {"id": ingredient_id, "detail": "Ingredient deleted"}


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

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="STOCK_MOVEMENT",
        table_name="ingredients",
        record_id=body.ingredient_id,
        new_values={"type": body.type, "quantity": body.quantity},
        ip_address=request.client.host if request.client else None,
    )
    return {
        "ingredient_id": body.ingredient_id,
        "new_stock": float(row["current_stock"]),
        "movement_type": body.type,
    }


@router.post("/ingredients/{ingredient_id}/stock", status_code=201)
async def add_stock(
    request: Request, ingredient_id: int, body: StockMovementCreate
) -> dict[str, Any]:
    """Add stock to an ingredient (shortcut). Admin/owner only."""
    require_admin_user(request)
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
                ingredient_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Ingredient not found")

            await conn.execute(
                format_sql(
                    """
                    INSERT INTO {}.stock_movements
                    (ingredient_id, type, quantity, comment, created_at)
                    VALUES ($1, 'incoming', $2, $3, NOW())
                    """,
                    tenant_schema,
                ),
                ingredient_id,
                body.quantity,
                body.comment,
            )

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="STOCK_INCOMING",
        table_name="ingredients",
        record_id=ingredient_id,
        new_values={"quantity": body.quantity},
        ip_address=request.client.host if request.client else None,
    )
    return {
        "ingredient_id": ingredient_id,
        "new_stock": float(row["current_stock"]),
    }


@router.get("/ingredients/low-stock")
async def list_low_stock(request: Request) -> list[dict[str, Any]]:
    """List ingredients with stock below minimum. Admin/owner only."""
    require_admin_user(request)
    tenant_schema = settings.get_tenant_schema(request.state.tenant_id)
    pool = await get_raw_pool()
    rows = await pool.fetch(
        format_sql(
            """
            SELECT * FROM {}.ingredients
            WHERE current_stock < min_stock
            ORDER BY name
            """,
            tenant_schema,
        )
    )
    return [dict(r) for r in rows]
