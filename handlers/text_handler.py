# handlers/text_handler.py — Captures description text that follows a photo upload (async).
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message
from handlers.photo_handler import register_photo_handler
from utils.logger import log_msg

def register_text_handler(bot: AsyncTeleBot):

    @bot.message_handler(func=lambda m: m.content_type == "text" and not m.text.startswith("/"))
    async def handle_text(message: Message):
        log_msg(f"[text_handler] Text message from {message.from_user.id}: {message.text[:50]}")
        telegram_id = message.from_user.id
        pending = register_photo_handler._pending 

        if telegram_id in pending:
            log_msg(f"[text_handler] Found pending photos for {telegram_id}, treating as description")
            description = message.text.strip()
            await register_photo_handler._finalize(bot, message, telegram_id, description)
        else:
            log_msg(f"[text_handler] No pending photo for {telegram_id}, sending help message")
            await bot.send_message(
                message.chat.id,
                "Сначала отправьте фото."
            )
