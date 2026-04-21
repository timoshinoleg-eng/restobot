# api/routes/menu.py
"""Menu and AI recommendation endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ai.rag_engine import RAGEngine
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()
rag_engine = RAGEngine()


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
    name: str
    description: Optional[str]
    price: float
    image_url: Optional[str]
    is_available: bool


@router.get("/menu", response_model=list[MenuItemResponse])
async def get_menu(request: Request) -> list[dict[str, Any]]:
    """Get all available menu items."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql(
        """
        SELECT id, name, description, price, image_url, is_available
        FROM {}.menu_items
        WHERE is_available = TRUE
        ORDER BY category_id, sort_order
        """,
        tenant_schema,
    )
    rows = await pool.fetch(query)

    return [dict(row) for row in rows]


@router.get("/menu/categories")
async def get_categories(request: Request) -> list[dict[str, Any]]:
    """Get menu categories."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql(
        """
        SELECT id, name, emoji, sort_order
        FROM {}.menu_categories
        WHERE is_active = TRUE
        ORDER BY sort_order
        """,
        tenant_schema,
    )
    rows = await pool.fetch(query)

    return [dict(row) for row in rows]


@router.post("/menu/ai-recommend", response_model=AIRecommendResponse)
async def ai_recommend(
    request: Request,
    body: AIRecommendRequest,
) -> dict[str, Any]:
    """AI-powered menu recommendation."""
    tenant_schema: str = request.state.tenant_schema
    tenant_id: str = request.state.tenant_id

    result = await rag_engine.recommend(
        tenant_schema=tenant_schema,
        tenant_id=tenant_id,
        query=body.query,
        user_id=body.user_id,
        max_price=body.max_price,
        exclude_allergens=body.exclude_allergens,
    )

    return result
