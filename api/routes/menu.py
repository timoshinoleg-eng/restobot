# api/routes/menu.py
"""Menu and AI recommendation endpoints."""

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


class AIRecommendRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    user_id: Optional[int] = Field(default=None, ge=1)
    max_price: Optional[float] = Field(default=None, gt=0)
    exclude_allergens: Optional[list[str]] = None


class DishResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    image_url: Optional[str]
    is_available: bool


class AIRecommendResponse(BaseModel):
    recommendation: str
    dishes: list[dict[str, Any]]
    total: float
    source: str
    latency_ms: float


class MenuItemResponse(BaseModel):
    id: int
    category_id: Optional[int]
    name: str
    description: Optional[str]
    price: float
    image_url: Optional[str]
    is_available: bool


class MenuItemCreate(BaseModel):
    category_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    image_url: Optional[str] = None
    is_available: bool = True
    sort_order: int = 0


class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    sort_order: Optional[int] = None


class MenuCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    emoji: Optional[str] = Field(default=None, max_length=16)
    sort_order: int = 0
    is_active: bool = True


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    emoji: Optional[str] = Field(default=None, max_length=16)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/menu", response_model=list[MenuItemResponse])
async def get_menu(
    request: Request,
    include_hidden: bool = False,
) -> list[dict[str, Any]]:
    """Get menu items. Admins can include hidden items via ?include_hidden=true."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    if include_hidden:
        require_admin_user(request)

    query = format_sql(
        """
        SELECT id, category_id, name, description, price, image_url, is_available
        FROM {}.menu_items
        WHERE 1=1
        """,
        tenant_schema,
    )
    if not include_hidden:
        query += " AND is_available = TRUE"
    query += " ORDER BY category_id, sort_order"

    rows = await pool.fetch(query)
    return [dict(row) for row in rows]


@router.get("/menu/categories")
async def get_categories(
    request: Request,
    include_hidden: bool = False,
) -> list[dict[str, Any]]:
    """Get menu categories. Admins can include hidden via ?include_hidden=true."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    if include_hidden:
        require_admin_user(request)

    query = format_sql(
        """
        SELECT id, name, emoji, sort_order
        FROM {}.menu_categories
        WHERE 1=1
        """,
        tenant_schema,
    )
    if not include_hidden:
        query += " AND is_active = TRUE"
    query += " ORDER BY sort_order"

    rows = await pool.fetch(query)
    return [dict(row) for row in rows]


@router.post("/menu", status_code=201)
async def create_menu_item(request: Request, body: MenuItemCreate) -> dict[str, Any]:
    """Create a new menu item. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            if body.category_id is not None:
                cat = await conn.fetchrow(
                    format_sql("SELECT id FROM {}.menu_categories WHERE id = $1", tenant_schema),
                    body.category_id,
                )
                if not cat:
                    raise HTTPException(status_code=422, detail="Category not found")

            row = await conn.fetchrow(
                format_sql(
                    """
                    INSERT INTO {}.menu_items
                    (category_id, name, description, price, image_url, is_available, sort_order)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    tenant_schema,
                ),
                body.category_id,
                body.name,
                body.description,
                body.price,
                body.image_url,
                body.is_available,
                body.sort_order,
            )

    assert row is not None
    item_id = int(row["id"])
    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="CREATE",
        table_name="menu_items",
        record_id=item_id,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.put("/menu/{item_id}")
async def update_menu_item(
    request: Request, item_id: int, body: MenuItemUpdate
) -> dict[str, Any]:
    """Update a menu item. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.menu_items WHERE id = $1", tenant_schema),
        item_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Menu item not found")

    fields: list[str] = []
    params: list[Any] = []

    if body.category_id is not None:
        fields.append("category_id = $" + str(len(params) + 1))
        params.append(body.category_id)
    if body.name is not None:
        fields.append("name = $" + str(len(params) + 1))
        params.append(body.name)
    if body.description is not None:
        fields.append("description = $" + str(len(params) + 1))
        params.append(body.description)
    if body.price is not None:
        fields.append("price = $" + str(len(params) + 1))
        params.append(body.price)
    if body.image_url is not None:
        fields.append("image_url = $" + str(len(params) + 1))
        params.append(body.image_url)
    if body.is_available is not None:
        fields.append("is_available = $" + str(len(params) + 1))
        params.append(body.is_available)
    if body.sort_order is not None:
        fields.append("sort_order = $" + str(len(params) + 1))
        params.append(body.sort_order)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    query = format_sql(
        f"""
        UPDATE {{}}.menu_items
        SET {', '.join(fields)}
        WHERE id = ${len(params) + 1}
        RETURNING *
        """,
        tenant_schema,
    )
    params.append(item_id)

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="menu_items",
        record_id=item_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.delete("/menu/{item_id}")
async def delete_menu_item(request: Request, item_id: int) -> dict[str, Any]:
    """Soft-delete (hide) a menu item. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.menu_items WHERE id = $1", tenant_schema),
        item_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Menu item not found")

    row = await pool.fetchrow(
        format_sql(
            """
            UPDATE {}.menu_items
            SET is_available = FALSE
            WHERE id = $1
            RETURNING id, name, is_available
            """,
            tenant_schema,
        ),
        item_id,
    )
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="DELETE",
        table_name="menu_items",
        record_id=item_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return {"id": item_id, "detail": "Menu item hidden"}


@router.post("/menu/categories", status_code=201)
async def create_category(request: Request, body: MenuCategoryCreate) -> dict[str, Any]:
    """Create a menu category. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    row = await pool.fetchrow(
        format_sql(
            """
            INSERT INTO {}.menu_categories (name, emoji, sort_order, is_active)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            tenant_schema,
        ),
        body.name,
        body.emoji,
        body.sort_order,
        body.is_active,
    )
    assert row is not None
    cat_id = int(row["id"])
    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="CREATE",
        table_name="menu_categories",
        record_id=cat_id,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.put("/menu/categories/{category_id}")
async def update_category(
    request: Request, category_id: int, body: MenuCategoryUpdate
) -> dict[str, Any]:
    """Update a menu category. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.menu_categories WHERE id = $1", tenant_schema),
        category_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Category not found")

    fields: list[str] = []
    params: list[Any] = []

    if body.name is not None:
        fields.append("name = $" + str(len(params) + 1))
        params.append(body.name)
    if body.emoji is not None:
        fields.append("emoji = $" + str(len(params) + 1))
        params.append(body.emoji)
    if body.sort_order is not None:
        fields.append("sort_order = $" + str(len(params) + 1))
        params.append(body.sort_order)
    if body.is_active is not None:
        fields.append("is_active = $" + str(len(params) + 1))
        params.append(body.is_active)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    query = format_sql(
        f"""
        UPDATE {{}}.menu_categories
        SET {', '.join(fields)}
        WHERE id = ${len(params) + 1}
        RETURNING *
        """,
        tenant_schema,
    )
    params.append(category_id)

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="menu_categories",
        record_id=category_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.delete("/menu/categories/{category_id}")
async def delete_category(request: Request, category_id: int) -> dict[str, Any]:
    """Delete a category if it has no items. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            items = await conn.fetchval(
                format_sql(
                    "SELECT COUNT(*) FROM {}.menu_items WHERE category_id = $1",
                    tenant_schema,
                ),
                category_id,
            )
            if items and int(items) > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Category contains menu items. Move or delete them first.",
                )

            old_row = await conn.fetchrow(
                format_sql("SELECT * FROM {}.menu_categories WHERE id = $1", tenant_schema),
                category_id,
            )
            if not old_row:
                raise HTTPException(status_code=404, detail="Category not found")

            await conn.execute(
                format_sql("DELETE FROM {}.menu_categories WHERE id = $1", tenant_schema),
                category_id,
            )

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="DELETE",
        table_name="menu_categories",
        record_id=category_id,
        old_values=dict(old_row),
        ip_address=request.client.host if request.client else None,
    )
    return {"id": category_id, "detail": "Category deleted"}
