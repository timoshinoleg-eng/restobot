# bot/main.py
"""Telegram bot entry point using aiogram 3.x."""

import asyncio
import logging
import signal
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import redis.asyncio as redis
from aiogram.fsm.storage.redis import RedisStorage

from ai.rag_engine import RAGEngine
from shared.config import get_settings
from shared.database import close_raw_pool, get_raw_pool, init_database
from shared.rate_limiter import RateLimiter
from shared.sql_utils import format_sql
from shared.telegram_user_tenants import (
    get_tenant_for_telegram_user,
    set_tenant_for_telegram_user,
)

settings = get_settings()
logger = logging.getLogger(__name__)
rag_engine = RAGEngine()

# Initialize bot and dispatcher
bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
_redis_client = redis.from_url(
    str(settings.REDIS_URL),
    decode_responses=True,  # type: ignore[no-untyped-call]
)
storage = RedisStorage(
    redis=_redis_client,
    state_ttl=3600,
    data_ttl=3600,
)
dp = Dispatcher(storage=storage)
router = Router()
rate_limiter = RateLimiter(limit=5, window=60)


# ─── FSM States ────────────────────────────────────────────────────


class UserFlow(StatesGroup):
    """Finite states for user interaction flow."""

    ai_recommend = State()
    order_type = State()
    order_address = State()
    order_phone = State()


# ─── Rate Limit Helper ─────────────────────────────────────────────


async def _check_rate_limit(message: Message) -> bool:
    """Check rate limit for user; send warning if exceeded."""
    if message.from_user is None:
        return False
    user_id = message.from_user.id
    if not await rate_limiter.is_allowed(user_id):
        remaining = await rate_limiter.remaining(user_id)
        await message.answer(f"⚠️ Слишком много запросов. Попробуйте через {remaining} сек.")
        return False
    return True


# ─── Tenant Helpers ────────────────────────────────────────────────


def _parse_deep_link_tenant(message: Message) -> str | None:
    """Extract tenant_id from /start <payload> deep link."""
    if not message.text:
        return None
    # Telegram deep link format: "/start <payload>"
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1].strip()


def _validate_tenant_id(tenant_id: str) -> bool:
    """Validate tenant_id using the same rules as schema naming."""
    if not tenant_id:
        return False
    try:
        settings.get_tenant_schema(tenant_id)
        return True
    except ValueError:
        return False


async def _get_user_tenant(state: FSMContext) -> str | None:
    """Retrieve tenant_id from FSM state data."""
    data = await state.get_data()
    return data.get("tenant_id")


_MISSING_TENANT_TEXT = (
    "⚠️ *Не удалось определить ресторан*\n\n"
    "Для использования бота перейдите по ссылке, "
    "предоставленной рестораном, или отсканируйте QR-код.\n\n"
    "Если у вас нет ссылки — свяжитесь с поддержкой: /support"
)


async def _require_tenant(message: Message, state: FSMContext) -> str | None:
    """Get tenant_id from state, then recover from DB mapping if needed."""
    tenant_id = await _get_user_tenant(state)
    if tenant_id is not None:
        return tenant_id

    if message.from_user is not None:
        tenant_id = await get_tenant_for_telegram_user(message.from_user.id)
        if tenant_id is not None and _validate_tenant_id(tenant_id):
            await state.update_data(tenant_id=tenant_id)
            return tenant_id

    if tenant_id is None:
        await message.answer(_MISSING_TENANT_TEXT)
        return None
    return tenant_id


def _telegram_external_ids(telegram_user_id: int) -> tuple[str, str]:
    """Return allowed external_id variants for Telegram users."""
    return (f"tg-{telegram_user_id}", str(telegram_user_id))


async def _get_tenant_user_data(tenant_id: str, telegram_user_id: int) -> dict[str, object] | None:
    """Fetch user profile and aggregate counters from tenant schema."""
    tenant_schema = settings.get_tenant_schema(tenant_id)
    external_ids = _telegram_external_ids(telegram_user_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            format_sql(
                """
                SELECT id, name, phone, email, loyalty_points
                FROM {}.users
                WHERE external_id = ANY($1::text[])
                  AND role = 'user'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                tenant_schema,
            ),
            list(external_ids),
        )
        if user_row is None:
            return None

        orders_count = await conn.fetchval(
            format_sql("SELECT COUNT(*) FROM {}.orders WHERE user_id = $1", tenant_schema),
            int(user_row["id"]),
        )
        last_order_at = await conn.fetchval(
            format_sql("SELECT MAX(created_at) FROM {}.orders WHERE user_id = $1", tenant_schema),
            int(user_row["id"]),
        )

    return {
        "id": int(user_row["id"]),
        "name": str(user_row["name"]),
        "phone": user_row["phone"],
        "email": user_row["email"],
        "loyalty_points": float(user_row["loyalty_points"]),
        "orders_count": int(orders_count or 0),
        "last_order_at": last_order_at,
    }


async def _anonymize_tenant_user_data(tenant_id: str, telegram_user_id: int) -> bool:
    """Anonymize a Telegram user in one tenant schema only."""
    tenant_schema = settings.get_tenant_schema(tenant_id)
    external_ids = _telegram_external_ids(telegram_user_id)
    anonym_suffix = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await conn.fetchval(
                format_sql(
                    """
                    SELECT id
                    FROM {}.users
                    WHERE external_id = ANY($1::text[])
                      AND role = 'user'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    tenant_schema,
                ),
                list(external_ids),
            )
            if user_id is None:
                return False

            await conn.execute(
                format_sql(
                    """
                    UPDATE {}.users
                    SET name = 'Deleted User',
                        phone = NULL,
                        email = NULL,
                        loyalty_points = 0,
                        external_id = CONCAT('deleted-', id::text, '-', $1),
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    tenant_schema,
                ),
                anonym_suffix,
                int(user_id),
            )
            await conn.execute(
                format_sql(
                    """
                    UPDATE {}.orders
                    SET phone = NULL,
                        address = NULL,
                        comment = NULL
                    WHERE user_id = $1
                    """,
                    tenant_schema,
                ),
                int(user_id),
            )
            await conn.execute(
                format_sql(
                    """
                    UPDATE {}.reservations
                    SET guest_name = 'Deleted User',
                        guest_phone = 'deleted'
                    WHERE user_id = $1
                    """,
                    tenant_schema,
                ),
                int(user_id),
            )

    return True


# ─── Commands ──────────────────────────────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command with optional deep-link tenant payload."""
    if not await _check_rate_limit(message):
        return
    await state.clear()

    user = message.from_user
    if user is None:
        return

    logger.debug("Processing /start for user %s", user.id)

    # Extract tenant from deep link payload
    tenant_id = _parse_deep_link_tenant(message)

    if tenant_id is None:
        # No deep link payload — try persisted mapping first
        tenant_id = await get_tenant_for_telegram_user(user.id)
        if tenant_id is None:
            # No mapping — check for configured default (dev/demo only)
            tenant_id = settings.TELEGRAM_BOT_DEFAULT_TENANT_ID
            if tenant_id is None:
                await message.answer(_MISSING_TENANT_TEXT)
                return
    elif not _validate_tenant_id(tenant_id):
        await message.answer(
            "⚠️ *Некорректная ссылка*\n\n"
            "Проверьте, что вы перешли по правильной ссылке. "
            "Если проблема повторяется — свяжитесь с поддержкой: /support"
        )
        return

    # Persist mapping in DB for recovery across sessions
    await set_tenant_for_telegram_user(user.id, tenant_id)

    # Persist tenant in FSM state for the entire session (runtime cache)
    await state.update_data(tenant_id=tenant_id)
    logger.info("User %s linked to tenant %s", user.id, tenant_id)

    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я — AI-ассистент ресторана. Помогу:\n"
        f"• 🍽️ Выбрать блюда по вашим предпочтениям\n"
        f"• 📋 Оформить заказ на доставку или самовывоз\n"
        f"• 🎁 Накопить бонусные баллы\n"
        f"• 📅 Забронировать столик\n\n"
        f"Начнём? 👇"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍽️ Посмотреть меню",
                    web_app=WebAppInfo(url=f"https://app.chatbot24.su/{tenant_id}/menu"),
                )
            ],
            [InlineKeyboardButton(text="🤖 AI-рекомендация", callback_data="ai_recommend")],
            [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
        ]
    )

    await message.answer(welcome_text, reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    """Show help message."""
    if not await _check_rate_limit(message):
        return
    await state.set_state(None)
    await message.answer(
        "🆘 *Помощь*\n\n"
        "/start — Главное меню\n"
        "/menu — Посмотреть меню\n"
        "/cart — Корзина\n"
        "/order — Оформить заказ\n"
        "/my_data — Мои данные\n"
        "/delete_account — Удалить данные\n"
        "/support — Связаться с поддержкой\n"
        "/help — Эта справка"
    )


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    """Show support contact."""
    if not await _check_rate_limit(message):
        return
    await message.answer(
        "📞 *Поддержка*\n\n" "Если возникли проблемы, напишите нам: support@restobot.ru"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    """Show menu categories with tenant-aware widget link."""
    if not await _check_rate_limit(message):
        return
    tenant_id = await _require_tenant(message, state)
    if tenant_id is None:
        return
    await message.answer(
        "🍽️ *Наше меню:*\n\nВыберите категорию 👇",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🍽️ Открыть меню",
                        web_app=WebAppInfo(url=f"https://app.chatbot24.su/{tenant_id}/menu"),
                    )
                ]
            ]
        ),
    )


@router.message(Command("cart"))
async def cmd_cart(message: Message, state: FSMContext) -> None:
    """Show current cart."""
    if not await _check_rate_limit(message):
        return
    tenant_id = await _require_tenant(message, state)
    if tenant_id is None:
        return
    await message.answer(
        f"🛒 *Ваша корзина*\n\n"
        f"Ресторан: {tenant_id}\n\n"
        f"[Cart items here]"
    )


@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext) -> None:
    """Start order flow with tenant-aware widget link."""
    if not await _check_rate_limit(message):
        return
    tenant_id = await _require_tenant(message, state)
    if tenant_id is None:
        return
    await state.set_state(UserFlow.order_type)
    await message.answer(
        "📋 *Оформление заказа*\n\nВыберите тип:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚚 Доставка", callback_data="order_delivery")],
                [InlineKeyboardButton(text="🏃 Самовывоз", callback_data="order_pickup")],
                [InlineKeyboardButton(text="🪑 В зале", callback_data="order_dinein")],
                [
                    InlineKeyboardButton(
                        text="📱 Оформить в приложении",
                        web_app=WebAppInfo(url=f"https://app.chatbot24.su/{tenant_id}/order"),
                    )
                ],
            ]
        ),
    )


@router.message(Command("my_data"))
async def cmd_my_data(message: Message, state: FSMContext) -> None:
    """Show user's personal data (152-ФЗ right to access)."""
    if not await _check_rate_limit(message):
        return
    if message.from_user is None:
        return
    tenant_id = await _require_tenant(message, state)
    if tenant_id is None:
        return

    user_data = await _get_tenant_user_data(tenant_id, message.from_user.id)
    if user_data is None:
        await message.answer(
            "🔒 *Ваши данные*\n\n"
            f"Ресторан: {tenant_id}\n"
            "Профиль не найден. Сначала оформите вход через веб-приложение ресторана."
        )
        return

    last_order_at = user_data["last_order_at"]
    last_order_text = (
        last_order_at.strftime("%Y-%m-%d %H:%M UTC") if isinstance(last_order_at, datetime) else "нет"
    )
    await message.answer(
        "🔒 *Ваши данные*\n\n"
        f"Ресторан: {tenant_id}\n"
        f"Имя: {user_data['name']}\n"
        f"Телефон: {user_data['phone'] or 'не указан'}\n"
        f"Email: {user_data['email'] or 'не указан'}\n"
        f"Баллы: {user_data['loyalty_points']:.2f}\n"
        f"Заказов: {user_data['orders_count']}\n"
        f"Последний заказ: {last_order_text}"
    )


@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message, state: FSMContext) -> None:
    """Right to be forgotten (152-ФЗ Article 14)."""
    if not await _check_rate_limit(message):
        return
    tenant_id = await _require_tenant(message, state)
    if tenant_id is None:
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")],
        ]
    )
    await message.answer(
        "⚠️ *Удаление данных*\n\n"
        f"Ресторан: {tenant_id}\n"
        "Все ваши персональные данные будут удалены. "
        "Заказы сохранятся в анонимизированном виде для бухгалтерии.\n\n"
        "Вы уверены?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "confirm_delete")
async def process_delete_account(callback: CallbackQuery, state: FSMContext) -> None:
    """Process account deletion."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    if callback.from_user is None:
        await callback.answer("Пользователь не определен")
        return

    tenant_id = await _require_tenant(callback.message, state)
    if tenant_id is None:
        await callback.answer()
        return
    deleted = await _anonymize_tenant_user_data(tenant_id, callback.from_user.id)
    if not deleted:
        await callback.message.edit_text(
            "ℹ️ *Данные не найдены*\n\n"
            f"Ресторан: {tenant_id}\n"
            "Профиль пользователя не найден, удалять нечего."
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "✅ *Данные удалены*\n\n"
        f"Ресторан: {tenant_id}\n"
        "Персональные данные удалены или анонимизированы в рамках текущего ресторана."
    )
    await callback.answer()


@router.callback_query(F.data == "ai_recommend")
async def process_ai_recommend(callback: CallbackQuery, state: FSMContext) -> None:
    """Start AI recommendation flow."""
    if callback.message is None:
        await callback.answer()
        return
    await state.set_state(UserFlow.ai_recommend)
    await callback.message.answer(
        "🤖 *AI-рекомендация*\n\n"
        "Опишите, что хотите:\n"
        "• 'Что посоветуешь на ужин?'\n"
        "• 'Нужно недорогое, но сытное'\n"
        "• 'Что есть веганского?'"
    )
    await callback.answer()


@router.message(UserFlow.ai_recommend, F.text)
async def handle_ai_text(message: Message, state: FSMContext) -> None:
    """Handle text in AI recommendation state."""
    if not await _check_rate_limit(message):
        return
    tenant_id = await _require_tenant(message, state)
    if tenant_id is None:
        return
    tenant_schema = settings.get_tenant_schema(tenant_id)

    await message.answer("🤖 Думаю над рекомендацией...")
    try:
        result = await rag_engine.recommend(
            tenant_schema=tenant_schema,
            tenant_id=tenant_id,
            query=message.text or "",
            user_id=message.from_user.id if message.from_user else None,
        )
        await message.answer(result["recommendation"], parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:
        logger.exception("AI recommendation failed: %s", exc)
        await message.answer(
            "🤖 Не удалось получить рекомендацию. Попробуйте позже или выберите блюда из /menu."
        )
    await state.set_state(None)


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext) -> None:
    """Handle text messages (default fallback)."""
    if not await _check_rate_limit(message):
        return
    await state.set_state(None)
    await message.answer(
        "Я не совсем понял 🤔\n\n"
        "Попробуйте:\n"
        "/menu — посмотреть меню\n"
        "/cart — корзина\n"
        "/order — оформить заказ\n"
        "/help — справка"
    )


# ─── Error Handler ─────────────────────────────────────────────────


@router.errors()
async def handle_error(event: types.ErrorEvent) -> None:
    """Global error handler with user-friendly messages."""
    update = event.update
    exception = event.exception
    logger.exception("Unhandled exception: %s", exception)

    if update.message:
        await update.message.answer(
            "😔 Произошла ошибка. Попробуйте позже или обратитесь в /support"
        )
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer("Ошибка обработки. Попробуйте позже.", show_alert=True)


# ─── Webhook / Polling ─────────────────────────────────────────────


async def on_startup() -> None:
    """Initialize on startup."""
    await init_database()

    if settings.TELEGRAM_WEBHOOK_URL:
        await bot.set_webhook(
            url=settings.TELEGRAM_WEBHOOK_URL,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        )
        logger.info("Webhook set: %s", settings.TELEGRAM_WEBHOOK_URL)
    else:
        await bot.delete_webhook()
        logger.info("Webhook deleted, using polling")


async def on_shutdown() -> None:
    """Cleanup on shutdown with graceful close."""
    logger.info("Shutting down bot...")
    await bot.session.close()
    await close_raw_pool()
    logger.info("Bot shutdown complete")


def main() -> None:
    """Entry point with graceful shutdown."""
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    if settings.TELEGRAM_WEBHOOK_URL:
        # Webhook mode (production)
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        )
        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def start() -> None:
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 8000)  # nosec B104
            await site.start()
            logger.info("Webhook server started on port 8000")

        loop.run_until_complete(start())

        # Graceful shutdown via signals
        stop_event = asyncio.Event()

        def _signal_handler(sig: int) -> None:
            logger.info("Received signal %s, shutting down...", sig)
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler, sig)

        try:
            loop.run_until_complete(stop_event.wait())
        finally:
            loop.run_until_complete(runner.cleanup())
            loop.run_until_complete(on_shutdown())
            loop.close()
    else:
        # Polling mode (development)
        asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
