# ai/rag_engine.py
"""RAG (Retrieval-Augmented Generation) engine for menu recommendations."""

import hashlib
import logging
import time
import uuid
from typing import Any, Optional

import httpx

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.redis_client import get_cache, set_cache
from shared.sql_utils import format_sql

settings = get_settings()
logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for external API calls."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: int = 0
        self._last_failure_time: Optional[float] = None
        self._state: str = "closed"  # closed, open, half-open

    def record_success(self) -> None:
        """Record a successful call."""
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.error("Circuit breaker opened after %s failures", self._failures)

    def can_execute(self) -> bool:
        """Check if call is allowed."""
        if self._state == "closed":
            return True
        if self._state == "open":
            if self._last_failure_time and (
                time.time() - self._last_failure_time > self.recovery_timeout
            ):
                self._state = "half-open"
                return True
            return False
        return True  # half-open


class YandexGPTClient:
    """Client for Yandex Foundation Models API with retry and circuit breaker."""

    def __init__(self) -> None:
        self.iam_token: Optional[str] = None
        self.token_expires: float = 0.0
        self.client = httpx.AsyncClient(timeout=30.0)
        self.circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

    async def _get_iam_token(self) -> str:
        """Get IAM token from YC Metadata Service or env."""
        if self.iam_token and time.time() < self.token_expires:
            return self.iam_token

        if settings.YC_IAM_TOKEN:
            self.iam_token = settings.YC_IAM_TOKEN
            self.token_expires = time.time() + 3600
            return self.iam_token

        # Get from metadata service (inside YC VM)
        resp = await self.client.get(
            (
                "http://169.254.169.254/computeMetadata/v1/"
                "instance/service-accounts/default/token"
            ),
            headers={"Metadata-Flavor": "Google"},
            timeout=5.0,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        token = data.get("access_token")
        if not isinstance(token, str):
            raise RuntimeError("Invalid IAM token response from metadata service")
        self.iam_token = token
        expires_in = data.get("expires_in", 3600)
        self.token_expires = time.time() + expires_in - 300
        return self.iam_token

    async def embed(self, text: str) -> list[float]:
        """Get text embedding vector with timeout and retry."""
        if not self.circuit.can_execute():
            raise RuntimeError("Circuit breaker is OPEN for YandexGPT embed")

        token = await self._get_iam_token()
        last_exception: Optional[Exception] = None

        for attempt in range(1, 4):
            try:
                resp = await self.client.post(
                    ("https://llm.api.cloud.yandex.net/" "foundationModels/v1/textEmbedding"),
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "modelUri": (f"emb://{settings.YC_FOLDER_ID}/text-search-doc/latest"),
                        "text": text,
                    },
                    timeout=settings.YANDEXGPT_EMBED_TIMEOUT,
                )
                resp.raise_for_status()
                result: list[float] = resp.json()["embedding"]
                self.circuit.record_success()
                return result
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                logger.warning("YandexGPT embed timeout (attempt %s): %s", attempt, exc)
                await self._backoff(attempt)
            except Exception as exc:
                last_exception = exc
                logger.error("YandexGPT embed error (attempt %s): %s", attempt, exc)
                self.circuit.record_failure()
                raise

        self.circuit.record_failure()
        raise RuntimeError("YandexGPT embed failed after 3 attempts") from last_exception

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        """Generate text with YandexGPT with timeout and retry."""
        if not self.circuit.can_execute():
            raise RuntimeError("Circuit breaker is OPEN for YandexGPT generate")

        token = await self._get_iam_token()
        model_uri = f"gpt://{settings.YC_FOLDER_ID}/{settings.YANDEXGPT_MODEL}"
        last_exception: Optional[Exception] = None

        for attempt in range(1, 4):
            try:
                resp = await self.client.post(
                    ("https://llm.api.cloud.yandex.net/" "foundationModels/v1/completion"),
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "modelUri": model_uri,
                        "completionOptions": {
                            "stream": False,
                            "temperature": temperature,
                            "maxTokens": max_tokens,
                        },
                        "messages": [
                            {"role": "system", "text": system_prompt},
                            {"role": "user", "text": user_message},
                        ],
                    },
                    timeout=settings.YANDEXGPT_TIMEOUT,
                )
                resp.raise_for_status()
                result: str = resp.json()["result"]["alternatives"][0]["message"]["text"]
                self.circuit.record_success()
                return result
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                logger.warning("YandexGPT generate timeout (attempt %s): %s", attempt, exc)
                await self._backoff(attempt)
            except Exception as exc:
                last_exception = exc
                logger.error("YandexGPT generate error (attempt %s): %s", attempt, exc)
                self.circuit.record_failure()
                raise

        self.circuit.record_failure()
        raise RuntimeError("YandexGPT generate failed after 3 attempts") from last_exception

    @staticmethod
    async def _backoff(attempt: int) -> None:
        """Exponential backoff delay."""
        await __import__("asyncio").sleep(0.5 * (2 ** (attempt - 1)))


class FallbackEngine:
    """Deterministic fallback when YandexGPT is unavailable."""

    @staticmethod
    def format_recommendation(dishes: list[dict[str, Any]], total: float) -> str:
        dishes_text = "\n\n".join(
            [
                f"*{i+1}. {d['name']}* — {d['price']:.0f} ₽\n" f"_{d.get('description', '')[:100]}_"
                for i, d in enumerate(dishes[:3])
            ]
        )
        return (
            f"\n🍽️ *Рекомендую попробовать:*\n\n"
            f"{dishes_text}\n\n"
            f"💰 *Итого:* {total:.0f} ₽\n\n"
            f"Нажмите кнопку ниже, чтобы добавить в корзину 👇\n"
        )


class RAGEngine:
    """Main RAG engine for menu recommendations."""

    def __init__(self) -> None:
        self.ygpt = YandexGPTClient()
        self.fallback = FallbackEngine()

    async def recommend(
        self,
        tenant_schema: str,
        tenant_id: str,
        query: str,
        user_id: Optional[int] = None,
        max_price: Optional[float] = None,
        exclude_allergens: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get AI recommendation for menu items."""
        request_id = str(uuid.uuid4())
        start = time.time()
        pool = await get_raw_pool()

        # Try to get embedding from cache
        cache_key = self._embedding_cache_key(query)
        cached_embedding: Optional[list[float]] = await get_cache(cache_key)

        try:
            if cached_embedding:
                query_embedding = cached_embedding
            else:
                query_embedding = await self.ygpt.embed(query)
                await set_cache(cache_key, query_embedding, settings.AI_CACHE_TTL)

            # Vector search with filters
            where_clauses = ["is_available = TRUE"]
            params: list[Any] = [query_embedding, settings.AI_TOP_K_RETRIEVAL]

            if max_price:
                params.append(max_price)
                where_clauses.append(f"price <= ${len(params)}")

            if exclude_allergens:
                params.append(exclude_allergens)
                where_clauses.append(f"NOT (allergens && ${len(params)}::varchar[])")

            where_sql = " AND ".join(where_clauses)

            query = format_sql(
                """
                SELECT
                    id, name, description, ingredients, price,
                    old_price, image_url, weight, calories, tags, allergens,
                    1 - (embedding <=> $1::vector) as similarity
                FROM {}.menu_items
                WHERE {where_sql}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                tenant_schema,
            ).format(where_sql=where_sql)
            rows = await pool.fetch(query, *params)

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
                    "similarity": float(r["similarity"]),
                }
                for r in rows
                if float(r["similarity"]) >= settings.AI_MIN_SIMILARITY
            ]

            if not dishes:
                # Fallback to popular items
                query = format_sql(
                    """
                    SELECT * FROM {}.menu_items
                    WHERE is_popular = TRUE AND is_available = TRUE
                    LIMIT 3
                    """,
                    tenant_schema,
                )
                rows = await pool.fetch(query)
                dishes = [dict(r) for r in rows]

            # Generate recommendation
            system_prompt = (
                "Ты — AI-сомелье ресторана. Помогаешь гостям выбирать блюда.\n\n"
                "Правила:\n"
                "1. Дружелюбный, профессиональный тон\n"
                "2. Учитывай аллергены и предпочтения\n"
                "3. Предлагай сочетания (напиток + основное + десерт)\n"
                "4. Не навязывай — давай выбор\n"
                "5. Цены прозрачно\n"
                "6. Максимум 3 предложения\n"
                "7. Не выдумывай блюда которых нет в меню"
            )

            context = "\n".join(
                [
                    f"- {d['name']} ({d['price']:.0f} ₽) — {d.get('description', '')[:80]}"
                    for d in dishes
                ]
            )

            user_prompt = (
                f'Запрос клиента: "{query}"\n\n'
                f"Найденные блюда:\n"
                f"{context}\n\n"
                f"Составь персонализированную рекомендацию. "
                f"Будь дружелюбным и кратким."
            )

            recommendation = await self.ygpt.generate(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.4,
                max_tokens=400,
            )
            source = "yandexgpt"

        except (httpx.TimeoutException, httpx.ConnectError, RuntimeError) as exc:
            logger.warning("YandexGPT error (request_id=%s), using fallback: %s", request_id, exc)

            if not settings.AI_FALLBACK_ENABLED:
                raise

            # Expanded fallback: category-based + popular items
            query = format_sql(
                """
                SELECT *
                FROM {}.menu_items
                WHERE is_popular = TRUE AND is_available = TRUE
                ORDER BY category_id, sort_order
                LIMIT 3
                """,
                tenant_schema,
            )
            rows = await pool.fetch(query)
            dishes = [dict(r) for r in rows]

            recommendation = self.fallback.format_recommendation(
                dishes,
                sum(d["price"] for d in dishes),
            )
            source = "fallback"

        latency = (time.time() - start) * 1000

        return {
            "recommendation": recommendation,
            "dishes": dishes,
            "total": sum(d["price"] for d in dishes),
            "source": source,
            "latency_ms": round(latency, 2),
            "request_id": request_id,
        }

    @staticmethod
    def _embedding_cache_key(query: str) -> str:
        """Generate deterministic cache key for query embedding."""
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return f"rag:embed:{digest}"
