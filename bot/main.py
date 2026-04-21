# bot/main.py
"""Telegram bot entry point using aiogram 3.x."""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from shared.config import get_settings
from shared.database import get_raw_pool, init_database

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher()
router = Router()

# ─── Commands ──────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    user = message.from_user
    
    # Get or create user in database
    pool = await get_raw_pool()
    # ... user management logic
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я — AI-ассистент ресторана. Помогу:
• 🍽️ Выбрать блюда по вашим предпочтениям
• 📋 Оформить заказ на доставку или самовывоз
• 🎁 Накопить бонусные баллы
• 📅 Забронировать столик

Начнём? 👇
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽️ Посмотреть меню", web_app=WebAppInfo(url=f"https://app.restobot.ru/{tenant_id}/menu"))],
        [InlineKeyboardButton(text="🤖 AI-рекомендация", callback_data="ai_recommend")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
    ])
    
    await message.answer(welcome_text, reply_markup=keyboard)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Show menu categories."""
    # Fetch categories from database
    # ...
    await message.answer("🍽️ *Наше меню:*\n\nВыберите категорию 👇")


@router.message(Command("cart"))
async def cmd_cart(message: Message):
    """Show current cart."""
    # Get cart from Redis
    # ...
    await message.answer("🛒 *Ваша корзина:*\n\n[Cart items here]")


@router.message(Command("order"))
async def cmd_order(message: Message):
    """Start order flow."""
    await message.answer("📋 *Оформление заказа*\n\nВыберите тип:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Доставка", callback_data="order_delivery")],
        [InlineKeyboardButton(text="🏃 Самовывоз", callback_data="order_pickup")],
        [InlineKeyboardButton(text="🪑 В зале", callback_data="order_dinein")],
    ]))


@router.message(Command("my_data"))
async def cmd_my_data(message: Message):
    """Show user's personal data (152-ФЗ right to access)."""
    # Fetch user data
    # ...
    await message.answer("""
🔒 *Ваши данные:*

Имя: [name]
Телефон: +7-XXX-XXX-XX-12
Адрес: [address]
Баллы: [points]

[✏️ Изменить] [🗑️ Удалить все данные]
""")


@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message):
    """Right to be forgotten (152-ФЗ Article 14)."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")],
    ])
    await message.answer(
        "⚠️ *Удаление данных*\n\nВсе ваши персональные данные будут удалены. "
        "Заказы сохранятся в анонимизированном виде для бухгалтерии.\n\n"
        "Вы уверены?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "confirm_delete")
async def process_delete_account(callback: CallbackQuery):
    """Process account deletion."""
    # Call anonymization function
    # ...
    await callback.message.edit_text("✅ *Данные удалены*\n\nВаши персональные данные полностью удалены.")
    await callback.answer()


@router.callback_query(F.data == "ai_recommend")
async def process_ai_recommend(callback: CallbackQuery):
    """Start AI recommendation flow."""
    await callback.message.answer(
        "🤖 *AI-рекомендация*\n\n"
        "Опишите, что хотите:\n"
        "• 'Что посоветуешь на ужин?'\n"
        "• 'Нужно недорогое, но сытное'\n"
        "• 'Что есть веганского?'"
    )
    await callback.answer()


@router.message(F.text)
async def handle_text(message: Message):
    """Handle text messages (potential AI queries)."""
    # Check if user is in AI recommendation flow
    # If yes, send to AI service
    # ...
    
    # Default: echo with help
    await message.answer(
        "Я не совсем понял 🤔\n\n"
        "Попробуйте:\n"
        "/menu — посмотреть меню\n"
        "/cart — корзина\n"
        "/order — оформить заказ\n"
        "/ai_recommend — AI-помощник"
    )


# ─── Webhook / Polling ───────────────────────────────────────────────

async def on_startup():
    """Initialize on startup."""
    await init_database()
    
    if settings.TELEGRAM_WEBHOOK_URL:
        await bot.set_webhook(
            url=settings.TELEGRAM_WEBHOOK_URL,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        )
        logger.info(f"Webhook set: {settings.TELEGRAM_WEBHOOK_URL}")
    else:
        await bot.delete_webhook()
        logger.info("Webhook deleted, using polling")


async def on_shutdown():
    """Cleanup on shutdown."""
    await bot.session.close()


def main():
    """Entry point."""
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    if settings.TELEGRAM_WEBHOOK_URL:
        # Webhook mode (production)
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web
        
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        )
        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        
        web.run_app(app, host="0.0.0.0", port=8000)
    else:
        # Polling mode (development)
        asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
