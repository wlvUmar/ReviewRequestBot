import telebot
from telebot.types import Message
from services.request_service import RequestService
from db.repository import BotRepository

# In-memory pending state: telegram_id -> file_id
# For multi-process deployments, move this to Redis or the bot DB table.
_pending_photos: dict[int, str] = {}

def register_photo_handler(bot: telebot.TeleBot):

    @bot.message_handler(content_types=["photo"])
    def handle_photo(message: Message):
        telegram_id = message.from_user.id

        # Take the highest resolution version of the photo
        photo = message.photo[-1]
        file_id = photo.file_id

        _pending_photos[telegram_id] = file_id

        bot.send_message(
            message.chat.id,
            "📸 Photo received!\n\n"
            "Add an optional <b>description</b> (brand, condition, notes) and send it as a message.\n"
            "Or send /submit to submit without a description."
        )

    @bot.message_handler(commands=["submit"])
    def handle_submit_no_desc(message: Message):
        telegram_id = message.from_user.id
        _finalize_submission(bot, message, telegram_id, description="")

    def _finalize_submission(bot, message: Message, telegram_id: int, description: str):
        file_id = _pending_photos.pop(telegram_id, None)
        if not file_id:
            bot.send_message(message.chat.id, "⚠️ No photo found. Please send a photo first.")
            return

        bot.send_message(message.chat.id, "⏳ Submitting your request, please wait…")

        repo = BotRepository()
        svc = RequestService(bot, repo)
        svc.submit_product_request(
            chat_id=message.chat.id,
            telegram_id=telegram_id,
            file_id=file_id,
            description=description,
        )

    # Expose _finalize_submission so text_handler can call it
    register_photo_handler._finalize = _finalize_submission
    register_photo_handler._pending = _pending_photos