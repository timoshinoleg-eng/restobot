# ai/rag_engine.py
"""RAG (Retrieval-Augmented Generation) engine for menu recommendations."""

import asyncio
import logging
import time
from typing import List, Optional

import httpx

from shared.config import get_settings
from shared.database import get_raw_pool

settings = get_settings()
logger = logging.getLogger(__name__)


class YandexGPTClient:
    """Client for Yandex Foundation Models API."""
    
    def __init__(self):
        self.iam_token: Optional[str] = None
        self.token_expires: float = 0
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def _get_iam_token(self) -> str:
        """Get IAM token from YC Metadata Service."""
        if self.iam_token and time.time() < self.token_expires:
            return self.iam_token
        
        if settings.YC_IAM_TOKEN:
            self.iam_token = settings.YC_IAM_TOKEN
            self.token_expires = time.time() + 3600
            return self.iam_token
        
        # Get from metadata service (inside YC VM)
        resp = await self.client.get(
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"}
        )
        data = resp.json()
        self.iam_token = data["access_token"]
        self.token_expires = time.time() + data.get("expires_in", 3600) - 300
        return self.iam_token
    
    async def embed(self, text: str) -> List[float]:
        """Get text embedding vector."""
        token = await self._get_iam_token()
        
        resp = await self.client.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "modelUri": f"emb://{settings.YC_FOLDER_ID}/text-search-doc/latest",
                "text": text
            },
            timeout=settings.YANDEXGPT_EMBED_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> str:
        """Generate text with YandexGPT."""
        token = await self._get_iam_token()
        model_uri = f"gpt://{settings.YC_FOLDER_ID}/{settings.YANDEXGPT_MODEL}"
        
        resp = await self.client.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "modelUri": model_uri,
                "completionOptions": {
                    "stream": False,
                    "temperature": temperature,
                    "maxTokens": max_tokens
                },
                "messages": [
                    {"role": "system", "text": system_prompt},
                    {"role": "user", "text": user_message}
                ]
            },
            timeout=settings.YANDEXGPT_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()["result"]["alternatives"][0]["message"]["text"]


class FallbackEngine:
    """Deterministic fallback when YandexGPT is unavailable."""
    
    @staticmethod
    def format_recommendation(dishes: List[dict], total: float) -> str:
        dishes_text = "\n\n".join([
            f"*{i+1}. {d['name']}* — {d['price']:.0f} ₽\n"
            f"_{d.get('description', '')[:100]}_"
            for i, d in enumerate(dishes[:3])
        ])
        return f"""
🍽️ *Рекомендую попробовать:*

{dishes_text}

💰 *Итого:* {total:.0f} ₽

Нажмите кнопку ниже, чтобы добавить в корзину 👇
"""


class RAGEngine:
    """Main RAG engine for menu recommendations."""
    
    def __init__(self):
        self.ygpt = YandexGPTClient()
        self.fallback = FallbackEngine()
    
    async def recommend(
        self,
        tenant_schema: str,
        tenant_id: str,
        query: str,
        user_id: Optional[int] = None,
        max_price: Optional[float] = None,
        exclude_allergens: Optional[List[str]] = None,
    ) -> dict:
        """Get AI recommendation for menu items."""
        start = time.time()
        pool = await get_raw_pool()
        
        try:
            # Step 1: Embed query
            query_embedding = await self.ygpt.embed(query)
            
            # Step 2: Vector search with filters
            where_clauses = ["is_available = TRUE"]
            params = [query_embedding, settings.AI_TOP_K_RETRIEVAL]
            
            if max_price:
                params.append(max_price)
                where_clauses.append(f"price <= ${len(params)}")
            
            if exclude_allergens:
                params.append(exclude_allergens)
                where_clauses.append(
                    f"NOT (allergens && ${len(params)}::varchar[])"
                )
            
            where_sql = " AND ".join(where_clauses)
            
            rows = await pool.fetch(f"""
                SELECT 
                    id, name, description, ingredients, price,
                    old_price, image_url, weight, calories, tags, allergens,
                    1 - (embedding <=> $1::vector) as similarity
                FROM {tenant_schema}.menu_items
                WHERE {where_sql}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, *params)
            
            dishes = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "description": r["description"],
                    "price": float(r["price"]),
                    "old_price": float(r["old_price"]) if r["old_price"] else None,
                    "image_url": r["image_url"],
                    "tags": r["tags"],
                    "allergens": r["allergens"],
                    "similarity": float(r["similarity"])
                }
                for r in rows
                if float(r["similarity"]) >= settings.AI_MIN_SIMILARITY
            ]
            
            if not dishes:
                # Fallback to popular items
                rows = await pool.fetch(f"""
                    SELECT * FROM {tenant_schema}.menu_items
                    WHERE is_popular = TRUE AND is_available = TRUE
                    LIMIT 3
                """)
                dishes = [dict(r) for r in rows]
            
            # Step 3: Generate recommendation
            system_prompt = """Ты — AI-сомелье ресторана. Помогаешь гостям выбирать блюда.

Правила:
1. Дружелюбный, профессиональный тон
2. Учитывай аллергены и предпочтения
3. Предлагай сочетания (напиток + основное + десерт)
4. Не навязывай — давай выбор
5. Цены прозрачно
6. Максимум 3 предложения
7. Не выдумывай блюда которых нет в меню"""
            
            context = "\n".join([
                f"- {d['name']} ({d['price']:.0f} ₽) — {d.get('description', '')[:80]}"
                for d in dishes
            ])
            
            user_prompt = f"""Запрос клиента: "{query}"

Найденные блюда:
{context}

Составь персонализированную рекомендацию. Будь дружелюбным и кратким."""
            
            recommendation = await self.ygpt.generate(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.4,
                max_tokens=400
            )
            
            source = "yandexgpt"
            
        except (httpx.TimeoutException, httpx.ConnectError, Exception) as e:
            logger.warning(f"YandexGPT error, using fallback: {e}")
            
            if not settings.AI_FALLBACK_ENABLED:
                raise
            
            # Fallback: get popular items
            rows = await pool.fetch(f"""
                SELECT * FROM {tenant_schema}.menu_items
                WHERE is_popular = TRUE AND is_available = TRUE
                LIMIT 3
            """)
            dishes = [dict(r) for r in rows]
            
            recommendation = self.fallback.format_recommendation(
                dishes,
                sum(d["price"] for d in dishes)
            )
            source = "fallback"
        
        latency = (time.time() - start) * 1000
        
        return {
            "recommendation": recommendation,
            "dishes": dishes,
            "total": sum(d["price"] for d in dishes),
            "source": source,
            "latency_ms": round(latency, 2)
        }
