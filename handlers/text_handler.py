# handlers/text_handler.py — Captures description text that follows a photo upload.
import telebot
from telebot.types import Message
from handlers.photo_handler import register_photo_handler

def register_text_handler(bot: telebot.TeleBot):

    @bot.message_handler(func=lambda m: m.content_type == "text" and not m.text.startswith("/"))
    def handle_text(message: Message):
        telegram_id = message.from_user.id
        pending = register_photo_handler._pending  # shared dict

        if telegram_id in pending:
            # User sent description after photo — proceed to submit
            description = message.text.strip()
            register_photo_handler._finalize(bot, message, telegram_id, description)
        else:
            bot.send_message(
                message.chat.id,
                "Please send a <b>photo</b> first, then I'll ask for a description."
            )