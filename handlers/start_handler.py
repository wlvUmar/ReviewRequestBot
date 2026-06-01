import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from db.repository import BotRepository
from utils.logger import get_logger
from utils.i18n import t

logger = get_logger(__name__)

_repo = BotRepository()


def register_start_handler(bot: AsyncTeleBot):
    async def _get_data(chat_id: int, user_id: int) -> dict:
        return await bot.current_states.get_data(chat_id, user_id) or {} #type:ignore

    async def _set_data(chat_id: int, user_id: int, data: dict) -> None:
        await bot.current_states.reset_data(chat_id, user_id)#type:ignore
        for key, value in data.items():
            await bot.current_states.set_data(chat_id, user_id, key, value)#type:ignore

    async def _get_state(chat_id: int, user_id: int):
        return await bot.get_state(user_id, chat_id=chat_id)

    async def _set_state(chat_id: int, user_id: int, state: str):
        await bot.set_state(user_id, state, chat_id=chat_id)

    def _clear_flow_data(data: dict) -> dict:
        data.pop("pending_photos", None)
        data.pop("pending_caption", None)
        data.pop("pending_albums", None)
        data.pop("pending_description", None)
        data.pop("preview", None)
        data.pop("desired_price", None)
        return data

    @bot.message_handler(commands=["start"])
    async def handle_start(message: Message):
        telegram_id = message.from_user.id

        # Block admin accounts from starting interactive flows
        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            return

        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""
        logger.debug(f"[start_handler] /start from {telegram_id} ({first_name})")

        await _repo.upsert_user(telegram_id, username, first_name)

        data = await _get_data(message.chat.id, telegram_id)
        lang = data.get("lang")

        data = _clear_flow_data(data)
        await _set_data(message.chat.id, telegram_id, data)

        if not lang:
            await _set_state(message.chat.id, telegram_id, "awaiting_lang")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🇺🇿uz", callback_data="lang:uz"), InlineKeyboardButton("🇷🇺ru", callback_data="lang:ru"))
            await bot.send_message(message.chat.id, t("ru", "choose_language"), reply_markup=markup)
            return

        user = await _repo.get_user(telegram_id)
        if user and user.get("phone"):
            await _set_state(message.chat.id, telegram_id, "awaiting_photo")
            logger.debug(f"[start_handler] Phone already on file for {telegram_id}, skipping ask")
            await _send_welcome(message, first_name, lang)
            return

        await _set_state(message.chat.id, telegram_id, "awaiting_phone")
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
        await bot.send_message(
            message.chat.id,
            t(lang, "phone_prompt"),
            reply_markup=markup
        )

    @bot.message_handler(content_types=["contact"])
    async def handle_contact(message: Message):
        telegram_id = message.from_user.id

        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
                return

        contact = message.contact
        data = await _get_data(message.chat.id, telegram_id)
        lang = data.get("lang", "ru")
        state = await _get_state(message.chat.id, telegram_id)

        if state == "awaiting_lang":
            await bot.send_message(message.chat.id, t(lang, "use_start_first"))
            return


        if contact and contact.user_id != telegram_id:
            await bot.send_message(
                message.chat.id,
                t(lang, "phone_not_own")
            )
            return

        phone = contact.phone_number if contact else ""
        if not phone:
            await bot.send_message(message.chat.id, t(lang, "phone_prompt"))
            return
        if not phone.startswith("+"):
            phone = "+" + phone

        logger.debug(f"[start_handler] Got phone for {telegram_id}: {phone}")

        await _repo.save_phone(telegram_id, phone)
        await _set_state(message.chat.id, telegram_id, "awaiting_photo")

        first_name = message.from_user.first_name or ""
        await _send_welcome(message, first_name, lang)

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("lang:"))
    async def handle_lang_callback(call: CallbackQuery):
        telegram_id = call.from_user.id

        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            await bot.answer_callback_query(call.id, "")
            return

        state = await _get_state(call.message.chat.id, telegram_id)
        if state != "awaiting_lang":
            data = await _get_data(call.message.chat.id, telegram_id)
            lang = data.get("lang", "ru")
            await bot.answer_callback_query(call.id, t(lang, "use_start_first"))
            return

        lang = call.data.split(":", 1)[1]
        if lang not in ("ru", "uz"):
            await bot.answer_callback_query(call.id, "Invalid language")
            return
        data = await _get_data(call.message.chat.id, telegram_id)
        data["lang"] = lang
        await _set_data(call.message.chat.id, telegram_id, data)
        await _set_state(call.message.chat.id, telegram_id, "awaiting_phone")

        try:
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            logger.warning("[start] Failed to Edit message")

        await bot.answer_callback_query(call.id, t(lang, "language_set"))

        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
        await bot.send_message(call.message.chat.id, t(lang, "phone_prompt"), reply_markup=markup)

    async def _send_welcome(message: Message, first_name: str, lang: str):
        await bot.send_message(
            message.chat.id,
            t(lang, "welcome", first_name=first_name, max_photos=Config.MAX_PHOTOS_PER_REQUEST),
            reply_markup=ReplyKeyboardRemove()
        )