# bot/notifier.py
"""Push notifications via Telegram bot."""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from shared.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def get_notifier_bot() -> Bot:
    """Get or create standalone bot instance for notifications."""
    global _bot
    if _bot is None:
        _bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
    return _bot


async def send_order_status_update(user_id: int, order_id: int, status: str) -> None:
    """Send order status update to user."""
    bot = get_notifier_bot()
    status_labels = {
        "new": "🆕 Новый",
        "confirmed": "✅ Подтверждён",
        "cooking": "👨‍🍳 Готовится",
        "ready": "🍽️ Готов",
        "delivered": "🚚 Доставлен",
        "cancelled": "❌ Отменён",
    }
    label = status_labels.get(status, status)
    text = f"📦 Заказ *#{order_id}* обновлён: {label}"
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as exc:
        logger.warning("Failed to send push to %s: %s", user_id, exc)
