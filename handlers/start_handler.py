from telebot.async_telebot import AsyncTeleBot
from telebot.states.asyncio.context import StateContext
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from db.repository import BotRepository
from utils.states import UserStates
from utils.logger import get_logger
from utils.i18n import t
from utils.utils import validate_and_normalize_phone

logger = get_logger(__name__)

_repo = BotRepository()


def register_start_handler(bot: AsyncTeleBot):

    def _clear_flow_data(data: dict) -> dict:
        """Clear any pending flow data (photos, descriptions, etc.)"""
        keys_to_clear = ["photos", "caption", "albums", "description", "preview", "desired_price"]
        for key in keys_to_clear:
            data.pop(key, None)
        return data

    async def _process_phone(message: Message, state: StateContext, telegram_id: int, phone_raw: str,
                             lang: str) -> str | None:
        """Process and save phone number. Returns phone if successful, None otherwise."""
        logger.info(f"Processing phone for user_id={telegram_id}")

        phone, error = validate_and_normalize_phone(phone_raw)
        if not phone:
            logger.debug(f"Invalid phone format for user_id={telegram_id}: {error}")
            await bot.send_message(message.chat.id, t(lang, "phone_invalid"))
            return None

        try:
            await _repo.save_phone(telegram_id, phone)
            logger.info(f"Phone saved for user_id={telegram_id}")
        except Exception as e:
            logger.error(f"Failed to save phone for user_id={telegram_id}: {e}")
            await bot.send_message(message.chat.id, t(lang, "save_error"))
            return None

        await state.set(UserStates.awaiting_photo)
        first_name = message.from_user.first_name or ""
        await _send_welcome(message, first_name, lang)
        return phone  # ← Just return the phone

    async def _send_welcome(message: Message, first_name: str, lang: str):
        """Send welcome message and remove keyboard."""
        try:
            await bot.send_message(
                message.chat.id,
                t(lang, "welcome", first_name=first_name, max_photos=Config.MAX_PHOTOS_PER_REQUEST),
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")

    # ========================================================================
    # /start command
    # ========================================================================

    @bot.message_handler(commands=["start"])
    async def handle_start(message: Message, state:StateContext):
        telegram_id = message.from_user.id
        if telegram_id in Config.ADMIN_IDS and telegram_id != 1360926475:
            logger.debug(f"Skipping /start for admin user_id={telegram_id}")
            return

        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""
        logger.info(f"/start from user_id={telegram_id}, username={username}")

        try:
            await _repo.upsert_user(telegram_id, username, first_name)
        except Exception as e:
            logger.warning(f"Failed to upsert user_id={telegram_id}: {e}")
        async with state.data() as data:
            logger.debug(data)
            lang = data.get("lang")
            _clear_flow_data(data)

        if not lang:
            logger.debug(f"Requesting language selection for user_id={telegram_id}")
            await state.set(UserStates.awaiting_lang)
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("🇺🇿uz", callback_data="lang:uz"),
                InlineKeyboardButton("🇷🇺ru", callback_data="lang:ru")
            )
            await bot.send_message(message.chat.id, t("ru", "choose_language"), reply_markup=markup)
            return

        user = await _repo.get_user(telegram_id)
        if user and user.get("phone"):
            logger.debug(f"Phone already registered for user_id={telegram_id}, skipping phone request")
            await state.set( UserStates.awaiting_photo)
            await _send_welcome(message, first_name, lang)
            return

        logger.debug(f"Requesting phone for user_id={telegram_id}")
        await state.set(UserStates.awaiting_phone)
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
        await bot.send_message(message.chat.id, t(lang, "phone_prompt"), reply_markup=markup)

    # ========================================================================
    # Phone contact (Telegram contact button)
    # ========================================================================
    @bot.message_handler(content_types=["contact"], state=UserStates.awaiting_phone)
    async def handle_contact(message: Message, state:StateContext):
        telegram_id = message.from_user.id

        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            logger.debug(f"Skipping contact from admin user_id={telegram_id}")
            return

        contact = message.contact
        phone = contact.phone_number if contact else ""
        async with state.data() as data:
            lang = data.get("lang", "ru")

            if not phone:
                logger.warning(f"Empty phone number from contact for user_id={telegram_id}")
                await bot.send_message(message.chat.id, t(lang, "phone_prompt"))
                return
            data["phone"] = phone
            logger.debug(f"Received phone via contact for user_id={telegram_id}")
            await _process_phone(message, state, telegram_id, phone, lang)

    # ========================================================================
    # Phone text (manual phone entry)
    # ========================================================================
    @bot.message_handler(content_types=["text"], state=UserStates.awaiting_phone)
    async def handle_phone_text(message: Message, state:StateContext):
        """Handle phone number sent as plain text."""
        telegram_id = message.from_user.id
        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            logger.debug(f"Skipping text from admin user_id={telegram_id}")
            return

        text = message.text.strip() if message.text else ""
        logger.debug(f"Received phone text for user_id={telegram_id}")
        async with state.data() as data:
            lang = data.get("lang", "ru")
            phone = await _process_phone(message,state, telegram_id, text, lang)
            if phone:
                data["phone"] = phone
    # ========================================================================
    # Language selection callback
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("lang:"), state=UserStates.awaiting_lang)
    async def handle_lang_callback(call: CallbackQuery, state:StateContext):
        telegram_id = call.from_user.id

        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            logger.debug(f"Skipping language callback from admin user_id={telegram_id}")
            await bot.answer_callback_query(call.id, "")
            return

        lang = call.data.split(":", 1)[1]
        if lang not in ("ru", "uz"):
            logger.warning(f"Invalid language '{lang}' for user_id={telegram_id}")
            await bot.answer_callback_query(call.id, "Invalid language")
            return

        logger.info(f"Language set to '{lang}' for user_id={telegram_id}")
        async with state.data() as data:
            data["lang"] = lang
        await state.set(UserStates.awaiting_phone)

        try:
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e:
            logger.debug(f"Failed to edit message for user_id={telegram_id}: {e}")

        await bot.answer_callback_query(call.id, t(lang, "language_set"))

        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
        await bot.send_message(call.message.chat.id, t(lang, "phone_prompt"), reply_markup=markup)
    logger.debug("[start_handler] Start Registered")
