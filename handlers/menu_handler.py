# handlers/menu_handler.py — commands (/help /cancel /lang /status) and the
# buttons that work in any state (cancel, new request, status, language).
# Registered FIRST so commands are never swallowed by the free-text handlers.
from telebot.async_telebot import AsyncTeleBot
from telebot.states.asyncio.context import StateContext
from telebot.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

from config import Config
from db.repository import BotRepository
from services.api_service import ApiService
from utils.flow import clear_flow_data, in_flow, is_ignored_admin
from utils.i18n import t
from utils.logger import get_logger
from utils.states import UserStates

logger = get_logger(__name__)

_repo = BotRepository()
_api = ApiService()


def register_menu_handler(bot: AsyncTeleBot):

    async def _lang(state: StateContext) -> str:
        async with state.data() as data:
            return data.get("lang") or "ru"

    async def _send_status(chat_id: int, state: StateContext) -> None:
        async with state.data() as data:
            lang = data.get("lang") or "ru"
            request_id = data.get("last_request_id")

        if not request_id:
            await bot.send_message(chat_id, t(lang, "status_none"))
            return

        info = None
        try:
            info = await _api.get_request_status(int(request_id))
        except Exception as e:
            logger.warning(f"[status] lookup failed request_id={request_id}: {e}")

        if not info:
            await bot.send_message(chat_id, t(lang, "status_error"))
            return

        status = (info.get("status") or "").lower()
        price = info.get("price") or ""
        if status == "approved" and price:
            text = t(lang, "status_approved", request_id=request_id, price=price)
        elif status == "rejected":
            text = t(lang, "status_rejected", request_id=request_id)
        else:
            text = t(lang, "status_pending", request_id=request_id)
        await bot.send_message(chat_id, text)

    async def _do_cancel(chat_id: int, state: StateContext) -> None:
        current = await state.get()
        async with state.data() as data:
            lang = data.get("lang") or "ru"
            clear_flow_data(data)
        if in_flow(current):
            await state.set(UserStates.awaiting_photo)
            await bot.send_message(chat_id, t(lang, "cancelled"))
        else:
            await bot.send_message(chat_id, t(lang, "use_start_first"))

    # ------------------------------------------------------------------ commands

    @bot.message_handler(commands=["help"])
    async def handle_help(message: Message, state: StateContext):
        if is_ignored_admin(message.from_user.id):
            return
        await bot.send_message(message.chat.id, t(await _lang(state), "help_text"), parse_mode="HTML")

    @bot.message_handler(commands=["cancel"])
    async def handle_cancel(message: Message, state: StateContext):
        if is_ignored_admin(message.from_user.id):
            return
        await _do_cancel(message.chat.id, state)

    @bot.message_handler(commands=["status"])
    async def handle_status(message: Message, state: StateContext):
        if is_ignored_admin(message.from_user.id):
            return
        await _send_status(message.chat.id, state)

    @bot.message_handler(commands=["lang"])
    async def handle_lang(message: Message, state: StateContext):
        if is_ignored_admin(message.from_user.id):
            return
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🇺🇿 uz", callback_data="setlang:uz"),
            InlineKeyboardButton("🇷🇺 ru", callback_data="setlang:ru"),
        )
        await bot.send_message(message.chat.id, t(await _lang(state), "lang_pick"), reply_markup=markup)

    # ------------------------------------------------------------------ buttons

    @bot.callback_query_handler(func=lambda call: bool(call.data) and call.data.startswith("setlang:"))
    async def handle_setlang(call: CallbackQuery, state: StateContext):
        if is_ignored_admin(call.from_user.id):
            await bot.answer_callback_query(call.id, "")
            return
        lang = call.data.split(":", 1)[1]
        if lang not in ("ru", "uz"):
            await bot.answer_callback_query(call.id, "Invalid language")
            return
        async with state.data() as data:
            data["lang"] = lang
        try:
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        await bot.answer_callback_query(call.id, t(lang, "language_set"))
        await bot.send_message(call.message.chat.id, t(lang, "language_set"))

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_flow")
    async def handle_cancel_button(call: CallbackQuery, state: StateContext):
        if is_ignored_admin(call.from_user.id):
            await bot.answer_callback_query(call.id, "")
            return
        await bot.answer_callback_query(call.id)
        try:
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        await _do_cancel(call.message.chat.id, state)

    @bot.callback_query_handler(func=lambda call: call.data == "status_check")
    async def handle_status_button(call: CallbackQuery, state: StateContext):
        await bot.answer_callback_query(call.id)
        await _send_status(call.message.chat.id, state)

    @bot.callback_query_handler(func=lambda call: call.data == "new_request")
    async def handle_new_request(call: CallbackQuery, state: StateContext):
        telegram_id = call.from_user.id
        if is_ignored_admin(telegram_id):
            await bot.answer_callback_query(call.id, "")
            return
        await bot.answer_callback_query(call.id)
        async with state.data() as data:
            lang = data.get("lang") or "ru"
            clear_flow_data(data)

        user = await _repo.get_user(telegram_id)
        if user and user.get("phone"):
            await state.set(UserStates.awaiting_photo)
            await bot.send_message(
                call.message.chat.id,
                t(lang, "new_request_prompt", max_photos=Config.MAX_PHOTOS_PER_REQUEST),
                parse_mode="HTML",
            )
            return

        await state.set(UserStates.awaiting_phone)
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
        await bot.send_message(call.message.chat.id, t(lang, "phone_prompt"), reply_markup=markup)

    logger.debug("[menu_handler] registered")
