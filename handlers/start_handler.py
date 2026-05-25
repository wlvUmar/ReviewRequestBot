from telebot.async_telebot import AsyncTeleBot
from config import Config
from services.request_service import RequestService
from db.repository import BotRepository
from utils.logger import log_msg

def register_start_handler(bot: AsyncTeleBot):
    @bot.message_handler(commands=["start"])
    async def handle_start(message):
        log_msg(f"[start_handler] /start command from {message.from_user.id} ({message.from_user.first_name})")
        telegram_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""

        log_msg(f"[start_handler] Upserting user: telegram_id={telegram_id}, username={username}, first_name={first_name}")
        repo = BotRepository()
        svc = RequestService(bot, repo)
        await svc.upsert_user(telegram_id, username, first_name)
        log_msg(f"[start_handler] User upserted, sending welcome message")

        await bot.send_message(
            message.chat.id,
            f"Здравствуйте, <b>{first_name}</b>!\n\n"
            "Отправьте фото товара.\n"
            f"Можно до {Config.MAX_PHOTOS_PER_REQUEST} фото за один запрос.\n"
            "После этого мы пришлём оценку сюда."
        )
