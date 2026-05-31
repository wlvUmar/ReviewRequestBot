import asyncio
from typing import TypedDict
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from config import Config
from services.request_service import RequestService
from db.repository import BotRepository
from utils.logger import get_logger
from utils.i18n import t

logger = get_logger(__name__)

class AlbumBatch(TypedDict):
    chat_id: int
    file_ids: list[str]


_repo = BotRepository()
_user_locks: dict[int, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()
_album_flush_timers: dict[tuple[int, int, str], asyncio.Task[None]] = {}


async def _get_user_lock(telegram_id: int) -> asyncio.Lock:
    async with _locks_guard:
        if telegram_id not in _user_locks:
            _user_locks[telegram_id] = asyncio.Lock()
        return _user_locks[telegram_id]


async def finalize_submission(bot: AsyncTeleBot, message: Message, telegram_id: int, description: str) -> None:
    chat_id = message.chat.id

    async def _get_data() -> dict:
        res = bot.current_states.get_data(chat_id, telegram_id) if bot.current_states else {}
        if asyncio.iscoroutine(res):
            res = await res
        return res or {}

    async def _set_data(data: dict) -> None:
        res = bot.current_states.reset_data(chat_id, telegram_id)  if bot.current_states else {}
        if asyncio.iscoroutine(res):
            await res
        for key, value in data.items():
            r = bot.current_states.set_data(chat_id, telegram_id, key, value)  if bot.current_states else {}
            if asyncio.iscoroutine(r):
                await r

    data = await _get_data()
    lang = data.get("lang", "ru")
    file_ids: list[str] = data.pop("pending_photos", [])
    caption: str = data.pop("pending_caption", "")
    desired_price: str = data.pop("desired_price", "")
    data.pop("pending_albums", None)
    data.pop("pending_description", None)
    preview = data.pop("preview", None)
    await _set_data(data)

    if caption and description:
        full_description = caption + "\n" + description
    else:
        full_description = caption or description

    if desired_price:
        full_description = f"{full_description}\n💰 {t(lang, 'desired_price_label')}: {desired_price}".strip()

    if not file_ids:
        await bot.send_message(chat_id, t(lang, "send_photo_first"))
        return

    try:
        if preview:
            await bot.delete_message(preview["chat_id"], preview["message_id"])
    except Exception:
        pass

    await bot.send_message(chat_id, f"⏳ Отправляем {len(file_ids)} фото на оценку...")
    svc = RequestService(bot, _repo)
    await svc.submit_product_request(
        chat_id=chat_id,
        telegram_id=telegram_id,
        file_ids=file_ids,
        description=full_description,
    )


def register_photo_handler(bot: AsyncTeleBot):
    async def _get_data(chat_id: int, user_id: int) -> dict:
        if bot.current_states:
            res = bot.current_states.get_data(chat_id, user_id)
            if asyncio.iscoroutine(res):
                res = await res
            return res or {}
        return {}

    async def _set_data(chat_id: int, user_id: int, data: dict) -> None:
        if bot.current_states:
            res = bot.current_states.reset_data(chat_id, user_id)
            if asyncio.iscoroutine(res):
                await res
            for key, value in data.items():
                r = bot.current_states.set_data(chat_id, user_id, key, value)
                if asyncio.iscoroutine(r):
                    await r

    async def _get_state(chat_id: int, user_id: int):
        res = bot.get_state(user_id, chat_id=chat_id)
        if asyncio.iscoroutine(res):
            res = await res
        return res

    async def _set_state(chat_id: int, user_id: int, state: str):
        res = bot.set_state(user_id, state, chat_id=chat_id)
        if asyncio.iscoroutine(res):
            await res

    @bot.message_handler(content_types=["photo"])
    async def handle_photo(message: Message):
        telegram_id = message.from_user.id
        chat_id = message.chat.id

        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            logger.debug(f"[photo_handler] Ignoring message from admin {telegram_id}")
            return

        user_lock = await _get_user_lock(telegram_id)

        data = await _get_data(chat_id, telegram_id)
        lang = data.get("lang", "ru")
        state = await _get_state(chat_id, telegram_id)

        user = await _repo.get_user(telegram_id)
        if not user or not user.get("phone"):
            await _set_state(chat_id, telegram_id, "awaiting_phone")
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
            await bot.send_message(chat_id, t(lang, "phone_prompt"), reply_markup=markup)
            return

        if state is None:
            await _set_state(chat_id, telegram_id, "awaiting_photo")
            state = "awaiting_photo"

        if state not in ("awaiting_photo", "awaiting_description"):
            await bot.send_message(chat_id, t(lang, "use_start_first"))
            return

        if message.photo:
            photo = message.photo[-1]
            file_id = photo.file_id
            media_group_id = getattr(message, "media_group_id", None)

            if media_group_id:
                await _queue_album_photo(message, telegram_id, media_group_id, file_id)
                return

        else: 
            file_id = "0"

        async with user_lock:
            data = await _get_data(chat_id, telegram_id)
            lang = data.get("lang", "ru")
            if not data.get("pending_photos") and not data.get("pending_albums"):
                data.pop("pending_description", None)
                data.pop("preview", None)
                data.pop("desired_price", None)
            if message.caption:
                data["pending_caption"] = message.caption

            current: list[str] = data.get("pending_photos", [])
            if len(current) >= Config.MAX_PHOTOS_PER_REQUEST:
                await bot.send_message(chat_id, t(lang, "photo_limit_reached", max=Config.MAX_PHOTOS_PER_REQUEST))
                return

            current.append(file_id)
            data["pending_photos"] = current
            await _set_data(chat_id, telegram_id, data)
            if data.get("desired_price"):
                await _set_state(chat_id, telegram_id, "awaiting_description")
            else:
                await _set_state(chat_id, telegram_id, "awaiting_price")
            count = len(current)

        prompt_key = "photo_progress" if data.get("desired_price") else "photo_received_ask_price"

        await bot.send_message(
            chat_id,
            t(lang, prompt_key, count=count, max=Config.MAX_PHOTOS_PER_REQUEST),
            parse_mode="HTML",
        )

    async def _queue_album_photo(message: Message, telegram_id: int, media_group_id: str, file_id: str) -> None:
        chat_id = message.chat.id
        user_lock = await _get_user_lock(telegram_id)
        async with user_lock:
            data = await _get_data(chat_id, telegram_id)
            if not data.get("pending_photos") and not data.get("pending_albums"):
                data.pop("pending_description", None)
                data.pop("preview", None)
                data.pop("desired_price", None)
            if message.caption:
                data["pending_caption"] = message.caption

            albums: dict[str, AlbumBatch] = data.get("pending_albums", {})
            batch = albums.get(media_group_id, {"chat_id": chat_id, "file_ids": []})
            if file_id not in batch["file_ids"] and len(batch["file_ids"]) < Config.MAX_PHOTOS_PER_REQUEST:
                batch["file_ids"].append(file_id)
                albums[media_group_id] = batch
                data["pending_albums"] = albums
                await _set_data(chat_id, telegram_id, data)

        timer_key = (chat_id, telegram_id, media_group_id)
        timer = _album_flush_timers.get(timer_key)
        if timer:
            timer.cancel()
        _album_flush_timers[timer_key] = asyncio.create_task(_flush_album_with_delay(chat_id, telegram_id, media_group_id))

    async def _flush_album_with_delay(chat_id: int, telegram_id: int, media_group_id: str) -> None:
        await asyncio.sleep(1.2)
        await _flush_album(chat_id, telegram_id, media_group_id)

    async def _flush_album(chat_id: int, telegram_id: int, media_group_id: str) -> None:
        _album_flush_timers.pop((chat_id, telegram_id, media_group_id), None)
        user_lock = await _get_user_lock(telegram_id)

        async with user_lock:
            data = await _get_data(chat_id, telegram_id)
            albums: dict[str, AlbumBatch] = data.get("pending_albums", {})
            batch = albums.pop(media_group_id, None)
            if not batch:
                return

            data["pending_albums"] = albums
            lang = data.get("lang", "ru")
            current: list[str] = data.get("pending_photos", [])
            room_left = Config.MAX_PHOTOS_PER_REQUEST - len(current)
            if room_left <= 0:
                await _set_data(chat_id, telegram_id, data)
                await bot.send_message(chat_id, t(lang, "photo_limit_reached", max=Config.MAX_PHOTOS_PER_REQUEST))
                return

            accepted = batch["file_ids"][:room_left]
            current.extend(accepted)
            data["pending_photos"] = current
            await _set_data(chat_id, telegram_id, data)
            current_state = await _get_state(chat_id, telegram_id)
            if data.get("desired_price"):
                if current_state != "awaiting_description":
                    await _set_state(chat_id, telegram_id, "awaiting_description")
            else:
                if current_state != "awaiting_price":
                    await _set_state(chat_id, telegram_id, "awaiting_price")
            count = len(current)

        prompt_key = "photo_progress" if data.get("desired_price") else "photo_received_ask_price"

        await bot.send_message(
            chat_id,
            t(lang, prompt_key, count=count, max=Config.MAX_PHOTOS_PER_REQUEST),
            parse_mode="HTML",
        )

    # Legacy fallback for old messages that still contain submit_request button.
    @bot.callback_query_handler(func=lambda call: call.data == "confirm_send")
    async def handle_confirm_send(call: CallbackQuery):
        telegram_id = call.from_user.id
        chat_id = call.message.chat.id

        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            logger.debug(f"[photo_handler] Ignoring confirm_send from admin {telegram_id}")
            await bot.answer_callback_query(call.id, "")
            return

        data = await _get_data(chat_id, telegram_id)
        lang = data.get("lang", "ru")
        pending = data.get("pending_photos", [])
        if not pending:
            await bot.answer_callback_query(call.id, t(lang, "send_photo_first"))
            return

        description = data.get("pending_description", "")
        # move to submitting state and finalize
        await _set_state(chat_id, telegram_id, "submitting")
        await bot.answer_callback_query(call.id, t(lang, "submit_button"))
        await finalize_submission(bot, call.message, telegram_id, description) #type:ignore
        await _set_state(chat_id, telegram_id, "awaiting_photo")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("show_contact:"))
    async def handle_show_contact_callback(call: CallbackQuery):
        phone = call.data.split("show_contact:", 1)[1].strip()
        await bot.answer_callback_query(call.id, f"Телефон: {phone}", show_alert=True)
