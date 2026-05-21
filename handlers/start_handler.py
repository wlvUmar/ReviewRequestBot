import telebot
from services.request_service import RequestService
from db.repository import BotRepository

def register_start_handler(bot: telebot.TeleBot):

    @bot.message_handler(commands=["start"])
    def handle_start(message: telebot.types.Message):
        telegram_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""

        repo = BotRepository()
        svc = RequestService(bot, repo)
        svc.upsert_user(telegram_id, username, first_name)

        bot.send_message(
            message.chat.id,
            f"👋 Hello, <b>{first_name}</b>!\n\n"
            "Send me a <b>photo</b> of a product and I'll submit it for review.\n"
            "You'll receive pricing and feedback once an admin reviews it."
        )