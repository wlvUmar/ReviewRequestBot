import asyncio

from telebot.async_telebot import AsyncTeleBot
from telebot.states.asyncio.context import StateContext
from telebot.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton

from config import Config
from db.repository import BotRepository
from services.request_service import RequestService
from utils.i18n import t
from utils.logger import get_logger
from utils.states import UserStates

logger = get_logger(__name__)

_repo = BotRepository()


async def finalize_submission(bot: AsyncTeleBot, state: StateContext, chat_id: int, telegram_id: int,
                              description: str) -> None:
    async with state.data() as data:
        lang = data.get("lang", "ru")
        file_ids: list[str] = data.pop("photos", [])
        caption: str = data.pop("caption", "")
        desired_price: str = data.pop("desired_price", "0")
        data.pop("albums", None)
        data.pop("description", None)

    full_description = "\n".join(filter(None, [caption, description]))
    if desired_price:
        full_description = f"{full_description}\n{t(lang, 'desired_price_label')}: {desired_price}".strip()

    if not file_ids:
        logger.warning(f"Submission attempt with no photos for user_id={telegram_id}")
        await bot.send_message(chat_id, t(lang, "send_photo_first"))
        return


    logger.info(f"Submitting request for user_id={telegram_id}: {len(file_ids)} photos")
    await bot.send_message(chat_id, t(lang, "submitting_request"))

    svc = RequestService(bot, _repo)
    await svc.submit_product_request(
        chat_id=chat_id,
        telegram_id=telegram_id,
        file_ids=file_ids,
        description=full_description,
        desired_price=desired_price,
        lang=lang
    )

def register_photo_handler(bot: AsyncTeleBot):
    _album_flush_timers: dict[tuple[int, int, str], asyncio.Task] = {}

    @bot.message_handler(content_types=["photo"], state=[UserStates.awaiting_photo, UserStates.awaiting_description])
    async def handle_photo(message: Message, state: StateContext):
        telegram_id = message.from_user.id
        chat_id = message.chat.id

        async with state.data() as data:
            lang = data.get("lang", "ru")

        user = await _repo.get_user(telegram_id)
        if not user or not user.get("phone"):
            logger.warning(f"Photo from unregistered user_id={telegram_id}, requesting phone")
            await state.set(UserStates.awaiting_phone)
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(t(lang, "share_phone"), request_contact=True))
            await bot.send_message(chat_id, t(lang, "phone_prompt"), reply_markup=markup)
            return

        file_id = message.photo[-1].file_id
        media_group_id = getattr(message, "media_group_id", None)

        if media_group_id:
            logger.debug(f"Photo in album from user_id={telegram_id}: {media_group_id}")
            await _queue_album_photo(state, message, telegram_id, media_group_id, file_id)
            return

        async with state.data() as data:
            if not data.get("photos") and not data.get("albums"):
                data.pop("description", None)
                data.pop("desired_price", None)

            if message.caption:
                data["caption"] = message.caption

            current: list[str] = data.get("photos", [])
            if len(current) >= Config.MAX_PHOTOS_PER_REQUEST:
                await bot.send_message(chat_id, t(lang, "photo_limit_reached", max=Config.MAX_PHOTOS_PER_REQUEST))
                return

            current.append(file_id)
            data["photos"] = current
            count = len(current)

        at_max = count >= Config.MAX_PHOTOS_PER_REQUEST
        key = "photo_progress_done" if at_max else "photo_progress_full"
        next_state = UserStates.awaiting_description

        await state.set(next_state)
        await bot.send_message(chat_id, t(lang, key, count=count, max=Config.MAX_PHOTOS_PER_REQUEST), parse_mode="HTML")
        logger.info(f"Photo accepted for user_id={telegram_id}: {count}/{Config.MAX_PHOTOS_PER_REQUEST}")

    async def _queue_album_photo(
            state: StateContext, message: Message, telegram_id: int, media_group_id: str, file_id: str
    ) -> None:
        chat_id = message.chat.id

        async with state.data() as data:
            if not data.get("photos") and not data.get("albums"):
                data.pop("description", None)
                data.pop("desired_price", None)

            if message.caption:
                data["caption"] = message.caption

            albums: dict[str, dict] = data.get("albums", {})
            batch = albums.get(media_group_id, {"chat_id": chat_id, "file_ids": []})

            if file_id not in batch["file_ids"] and len(batch["file_ids"]) < Config.MAX_PHOTOS_PER_REQUEST:
                batch["file_ids"].append(file_id)
                albums[media_group_id] = batch
                data["albums"] = albums

        timer_key = (chat_id, telegram_id, media_group_id)
        existing = _album_flush_timers.get(timer_key)
        if existing:
            existing.cancel()
        _album_flush_timers[timer_key] = asyncio.create_task(
            _flush_album_after_delay(state, chat_id, telegram_id, media_group_id)
        )

    async def _flush_album_after_delay(
            state: StateContext, chat_id: int, telegram_id: int, media_group_id: str
    ) -> None:
        await asyncio.sleep(1)
        _album_flush_timers.pop((chat_id, telegram_id, media_group_id), None)

        async with state.data() as data:
            albums: dict[str, dict] = data.get("albums", {})
            batch = albums.pop(media_group_id, None)

            if not batch:
                logger.debug(f"Album {media_group_id} already flushed for user_id={telegram_id}")
                return

            data["albums"] = albums
            lang = data.get("lang", "ru")
            current: list[str] = data.get("photos", [])
            room_left = Config.MAX_PHOTOS_PER_REQUEST - len(current)

            if room_left <= 0:
                await bot.send_message(chat_id, t(lang, "photo_limit_reached", max=Config.MAX_PHOTOS_PER_REQUEST))
                return

            accepted = batch["file_ids"][:room_left]
            current.extend(accepted)
            data["photos"] = current
            count = len(current)
            logger.info(f"Album flushed for user_id={telegram_id}: {len(accepted)} accepted, total {count}")

        at_max = count >= Config.MAX_PHOTOS_PER_REQUEST
        key = "photo_progress_done" if at_max else "photo_progress_full"
        await state.set(UserStates.awaiting_description)
        await bot.send_message(
            chat_id,
            t(lang, key, count=count, max=Config.MAX_PHOTOS_PER_REQUEST),
            parse_mode="HTML",
        )

    # confirm_send and show_contact callbacks stay exactly as they are — no changes needed
    @bot.callback_query_handler(func=lambda call: call.data == "confirm_send")
    async def handle_confirm_send(call: CallbackQuery, state: StateContext):
        telegram_id = call.from_user.id
        chat_id = call.message.chat.id

        async with state.data() as data:
            lang = data.get("lang", "ru")
            pending = data.get("photos", [])
            description = data.get("description", "")

        if not pending:
            logger.warning(f"Confirm send with no pending photos for user_id={telegram_id}")
            await bot.answer_callback_query(call.id, t(lang, "send_photo_first"))
            return

        await state.set(UserStates.submitting)
        await bot.answer_callback_query(call.id, t(lang, "submit_button"))
        await finalize_submission(bot, state, chat_id, telegram_id, description)
        await state.set(UserStates.awaiting_photo)
        logger.info(f"Submission finalized for user_id={telegram_id}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("show_contact:"))
    async def handle_show_contact_callback(call: CallbackQuery):
        if call.data:
            phone = call.data.split("show_contact:", 1)[1].strip()
            await bot.answer_callback_query(call.id, f"Телефон: {phone}", show_alert=True)