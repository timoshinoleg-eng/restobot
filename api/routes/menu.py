# api/routes/menu.py
"""Menu and AI recommendation endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ai.rag_engine import RAGEngine
from shared.config import get_settings
from shared.database import get_raw_pool

router = APIRouter()
settings = get_settings()
rag_engine = RAGEngine()


class AIRecommendRequest(BaseModel):
    query: str
    user_id: Optional[int] = None
    max_price: Optional[float] = None
    exclude_allergens: Optional[List[str]] = None


class AIRecommendResponse(BaseModel):
    recommendation: str
    dishes: List[dict]
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


@router.get("/menu", response_model=List[MenuItemResponse])
async def get_menu(request: Request):
    """Get all available menu items."""
    tenant_schema = request.state.tenant_schema
    pool = await get_raw_pool()
    
    rows = await pool.fetch(f"""
        SELECT id, name, description, price, image_url, is_available
        FROM {tenant_schema}.menu_items
        WHERE is_available = TRUE
        ORDER BY category_id, sort_order
    """)
    
    return [dict(row) for row in rows]


@router.get("/menu/categories")
async def get_categories(request: Request):
    """Get menu categories."""
    tenant_schema = request.state.tenant_schema
    pool = await get_raw_pool()
    
    rows = await pool.fetch(f"""
        SELECT id, name, emoji, sort_order
        FROM {tenant_schema}.menu_categories
        WHERE is_active = TRUE
        ORDER BY sort_order
    """)
    
    return [dict(row) for row in rows]


@router.post("/menu/ai-recommend", response_model=AIRecommendResponse)
async def ai_recommend(
    request: Request,
    body: AIRecommendRequest,
):
    """AI-powered menu recommendation."""
    tenant_schema = request.state.tenant_schema
    tenant_id = request.state.tenant_id
    
    result = await rag_engine.recommend(
        tenant_schema=tenant_schema,
        tenant_id=tenant_id,
        query=body.query,
        user_id=body.user_id,
        max_price=body.max_price,
        exclude_allergens=body.exclude_allergens,
    )
    
    return result
