from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import Config
from services.request_service import RequestService
from db.repository import BotRepository
from utils.logger import log_msg

_repo = BotRepository()

def register_start_handler(bot: AsyncTeleBot):

    @bot.message_handler(commands=["start"])
    async def handle_start(message: Message):
        telegram_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""
        log_msg(f"[start_handler] /start from {telegram_id} ({first_name})")

        await _repo.upsert_user(telegram_id, username, first_name)

        # Check if we already have their phone
        user = await _repo.get_user(telegram_id)
        if user and user.get("phone"):
            log_msg(f"[start_handler] Phone already on file for {telegram_id}, skipping ask")
            await _send_welcome(bot, message, first_name)
            return

        # Ask for phone
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton("📱 Поделиться номером", request_contact=True))

        await bot.send_message(
            message.chat.id,
            f"Здравствуйте, <b>{first_name}</b>!\n\n"
            "Для начала поделитесь вашим номером телефона — "
            "это нужно, чтобы мы могли связаться с вами по заявке.",
            reply_markup=markup
        )

    @bot.message_handler(content_types=["contact"])
    async def handle_contact(message: Message):
        telegram_id = message.from_user.id
        contact = message.contact

        # Security: make sure they're sharing their own contact, not someone else's
        if contact.user_id != telegram_id:
            await bot.send_message(
                message.chat.id,
                "⚠️ Пожалуйста, поделитесь своим собственным номером."
            )
            return

        phone = contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone

        log_msg(f"[start_handler] Got phone for {telegram_id}: {phone}")
        await _repo.save_phone(telegram_id, phone)

        first_name = message.from_user.first_name or ""
        await _send_welcome(bot, message, first_name)

    async def _send_welcome(bot: AsyncTeleBot, message: Message, first_name: str):
        await bot.send_message(
            message.chat.id,
            f"✅ Отлично, <b>{first_name}</b>!\n\n"
            "Отправьте фото товара.\n"
            f"Можно до {Config.MAX_PHOTOS_PER_REQUEST} фото за один запрос.\n"
            "После этого мы пришлём оценку сюда.",
            reply_markup=ReplyKeyboardRemove()
        )