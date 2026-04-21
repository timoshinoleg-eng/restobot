# bot/main.py
"""Telegram bot entry point using aiogram 3.x."""

import asyncio
import logging
import signal

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

from shared.config import get_settings
from shared.database import close_raw_pool, init_database
from shared.rate_limiter import RateLimiter

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher()
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


# ─── Commands ──────────────────────────────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""
    if not await _check_rate_limit(message):
        return
    await state.clear()

    user = message.from_user
    if user is None:
        return

    # TODO: Get or create user in database
    logger.debug("Ensuring DB pool for user %s", user.id)

    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я — AI-ассистент ресторана. Помогу:\n"
        f"• 🍽️ Выбрать блюда по вашим предпочтениям\n"
        f"• 📋 Оформить заказ на доставку или самовывоз\n"
        f"• 🎁 Накопить бонусные баллы\n"
        f"• 📅 Забронировать столик\n\n"
        f"Начнём? 👇"
    )

    # tenant_id должен приходить из deep-link или базы данных
    # Используем placeholder для MVP; в production — извлекать из контекста
    tenant_id = "default"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍽️ Посмотреть меню",
                    web_app=WebAppInfo(url=f"https://app.restobot.ru/{tenant_id}/menu"),
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
    await state.clear()
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
async def cmd_menu(message: Message) -> None:
    """Show menu categories."""
    if not await _check_rate_limit(message):
        return
    await message.answer("🍽️ *Наше меню:*\n\nВыберите категорию 👇")


@router.message(Command("cart"))
async def cmd_cart(message: Message) -> None:
    """Show current cart."""
    if not await _check_rate_limit(message):
        return
    await message.answer("🛒 *Ваша корзина:*\n\n[Cart items here]")


@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext) -> None:
    """Start order flow."""
    if not await _check_rate_limit(message):
        return
    await state.set_state(UserFlow.order_type)
    await message.answer(
        "📋 *Оформление заказа*\n\nВыберите тип:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚚 Доставка", callback_data="order_delivery")],
                [InlineKeyboardButton(text="🏃 Самовывоз", callback_data="order_pickup")],
                [InlineKeyboardButton(text="🪑 В зале", callback_data="order_dinein")],
            ]
        ),
    )


@router.message(Command("my_data"))
async def cmd_my_data(message: Message) -> None:
    """Show user's personal data (152-ФЗ right to access)."""
    if not await _check_rate_limit(message):
        return
    await message.answer(
        "🔒 *Ваши данные:*\n\n"
        "Имя: [name]\n"
        "Телефон: +7-XXX-XXX-XX-12\n"
        "Адрес: [address]\n"
        "Баллы: [points]\n\n"
        "[✏️ Изменить] [🗑️ Удалить все данные]"
    )


@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message) -> None:
    """Right to be forgotten (152-ФЗ Article 14)."""
    if not await _check_rate_limit(message):
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")],
        ]
    )
    await message.answer(
        "⚠️ *Удаление данных*\n\n"
        "Все ваши персональные данные будут удалены. "
        "Заказы сохранятся в анонимизированном виде для бухгалтерии.\n\n"
        "Вы уверены?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "confirm_delete")
async def process_delete_account(callback: CallbackQuery) -> None:
    """Process account deletion."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    # Call anonymization function
    # TODO: Implement actual anonymization
    await callback.message.edit_text(
        "✅ *Данные удалены*\n\n" "Ваши персональные данные полностью удалены."
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
    # TODO: Send query to AI service
    await message.answer("🤖 Думаю над рекомендацией... (заглушка)")
    await state.clear()


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext) -> None:
    """Handle text messages (default fallback)."""
    if not await _check_rate_limit(message):
        return
    await state.clear()
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
