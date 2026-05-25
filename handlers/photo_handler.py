# handlers/photo_handler.py — Captures product photos (async).
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from services.request_service import RequestService
from db.repository import BotRepository
from utils.logger import log_msg
 
# In-memory pending state: telegram_id -> [file_id, ...]
_pending_photos: dict[int, list[str]] = {}
# In-memory prompt message ids so we can remove the inline keyboard after submit.
_submit_prompt_messages: dict[int, int] = {}
# In-memory progress counters so older photo updates cannot overwrite newer ones.
_submit_progress_counts: dict[int, int] = {}
# In-memory album buffers keyed by Telegram media group id.
_pending_albums: dict[str, dict] = {}
# Async lock per-chat progress updates to keep photo album progress monotonic.
_photo_state_lock = asyncio.Lock()

def register_photo_handler(bot: AsyncTeleBot):

    @bot.message_handler(content_types=["photo"])
    async def handle_photo(message: Message):
        log_msg(f"[photo_handler] Photo received from {message.from_user.id}")
        telegram_id = message.from_user.id

        if message.photo:
            photo = message.photo[-1]
            file_id = photo.file_id
            media_group_id = getattr(message, "media_group_id", None)

            if media_group_id:
                await _queue_album_photo(bot, message, telegram_id, media_group_id, file_id)
                return

            async with _photo_state_lock:
                current = _pending_photos.get(telegram_id, [])
                if len(current) >= Config.MAX_PHOTOS_PER_REQUEST:
                    log_msg(f"[photo_handler] Photo limit reached for {telegram_id}")
                    await bot.send_message(
                        message.chat.id,
                        f"⚠️ You can send up to {Config.MAX_PHOTOS_PER_REQUEST} photos per request."
                    )
                    return

                current.append(file_id)
                _pending_photos[telegram_id] = current
                count = len(current)
                prev_prompt_id = _submit_prompt_messages.get(telegram_id)
                prev_progress = _submit_progress_counts.get(telegram_id, 0)
                if count <= prev_progress:
                    log_msg(f"[photo_handler] Skipping stale progress update for {telegram_id}: {count} <= {prev_progress}")
                    return
                _submit_progress_counts[telegram_id] = count
                log_msg(f"[photo_handler] Photo stored in pending: {file_id[:20]}... (total={count})")

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Отправить", callback_data="submit_request"))
            progress_text = (
                f"📸 <b>Фото принято:</b> {count}/{Config.MAX_PHOTOS_PER_REQUEST}\n\n"
                "📝 <b>Добавьте короткое описание:</b>\n"
                "— что это за вещь\n"
                "— желаемая цена продажи\n\n"
                "📷 Можно отправить ещё фото\n\n"
                "👉 Когда будете готовы — нажмите кнопку для оценки"
            )

            if prev_prompt_id:
                try:
                    async with _photo_state_lock:
                        if _submit_progress_counts.get(telegram_id, 0) != count:
                            log_msg(f"[photo_handler] Aborting stale delete for {telegram_id}: current={_submit_progress_counts.get(telegram_id, 0)} desired={count}")
                            return
                    # Delete previous message and send new one
                    await bot.delete_message(message.chat.id, prev_prompt_id)
                except Exception as e:
                    log_msg(f"[photo_handler] Failed to delete previous progress message: {e}")

            prompt = await bot.send_message(
                message.chat.id,
                progress_text,
                reply_markup=markup
            )
            async with _photo_state_lock:
                if _submit_progress_counts.get(telegram_id, 0) == count:
                    _submit_prompt_messages[telegram_id] = prompt.message_id

    async def _queue_album_photo(bot: AsyncTeleBot, message: Message, telegram_id: int, media_group_id: str, file_id: str) -> None:
        async with _photo_state_lock:
            batch = _pending_albums.get(media_group_id)
            if batch is None:
                batch = {
                    "telegram_id": telegram_id,
                    "chat_id": message.chat.id,
                    "file_ids": [],
                    "timer": None,
                }
                _pending_albums[media_group_id] = batch

            if len(batch["file_ids"]) >= Config.MAX_PHOTOS_PER_REQUEST:
                log_msg(f"[photo_handler] Album photo limit reached for {telegram_id} group={media_group_id}")
                return

            if file_id not in batch["file_ids"]:
                batch["file_ids"].append(file_id)
                log_msg(f"[photo_handler] Album buffered: group={media_group_id} total={len(batch['file_ids'])}")

            timer = batch.get("timer")
            if timer:
                timer.cancel()

            timer = asyncio.create_task(_flush_album_with_delay(bot, media_group_id))
            batch["timer"] = timer

    async def _flush_album_with_delay(bot: AsyncTeleBot, media_group_id: str) -> None:
        await asyncio.sleep(1.2)
        await _flush_album(bot, media_group_id)

    async def _flush_album(bot: AsyncTeleBot, media_group_id: str) -> None:
        async with _photo_state_lock:
            batch = _pending_albums.pop(media_group_id, None)

        if not batch:
            return

        telegram_id = batch["telegram_id"]
        chat_id = batch["chat_id"]
        file_ids = batch["file_ids"]
        if not file_ids:
            return

        async with _photo_state_lock:
            current = _pending_photos.get(telegram_id, [])
            room_left = Config.MAX_PHOTOS_PER_REQUEST - len(current)
            if room_left <= 0:
                log_msg(f"[photo_handler] Album flush skipped, limit reached for {telegram_id}")
                await bot.send_message(chat_id, f"⚠️ You can send up to {Config.MAX_PHOTOS_PER_REQUEST} photos per request.")
                return

            accepted = file_ids[:room_left]
            current.extend(accepted)
            _pending_photos[telegram_id] = current
            count = len(current)
            _submit_progress_counts[telegram_id] = count
            prev_prompt_id = _submit_prompt_messages.get(telegram_id)
            log_msg(f"[photo_handler] Album flushed for {telegram_id}: +{len(accepted)} total={count}")

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Отправить", callback_data="submit_request"))
        progress_text = (
            f"📸 Фото принято: {count}/{Config.MAX_PHOTOS_PER_REQUEST}\n\n"
            "Можно отправить ещё фото или текст.\n"
            "Нажмите кнопку ниже, чтобы отправить на оценку."
        )

        if prev_prompt_id:
            try:
                # Delete previous message and send new one
                await bot.delete_message(chat_id, prev_prompt_id)
            except Exception as e:
                log_msg(f"[photo_handler] Failed to delete album progress message: {e}")

        prompt = await bot.send_message(chat_id, progress_text, reply_markup=markup)
        async with _photo_state_lock:
            if _submit_progress_counts.get(telegram_id, 0) == count:
                _submit_prompt_messages[telegram_id] = prompt.message_id

    @bot.callback_query_handler(func=lambda call: call.data == "submit_request")
    async def handle_submit_callback(call: CallbackQuery):
        telegram_id = call.from_user.id
        log_msg(f"[photo_handler] Submit button clicked from {telegram_id}")
        await bot.answer_callback_query(call.id, "Отправляем...")

        prompt_id = _submit_prompt_messages.pop(telegram_id, None)
        _submit_progress_counts.pop(telegram_id, None)
        if prompt_id:
            try:
                await bot.edit_message_reply_markup(call.message.chat.id, prompt_id, reply_markup=None)
            except Exception as e:
                log_msg(f"[photo_handler] Failed to remove submit button: {e}")

        await _finalize_submission(bot, call.message, telegram_id, description="")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("show_contact:"))
    async def handle_show_contact_callback(call: CallbackQuery):
        phone = call.data.split("show_contact:", 1)[1].strip()
        log_msg(f"[photo_handler] Show contact clicked from {call.from_user.id}")
        await bot.answer_callback_query(call.id, f"Телефон: {phone}", show_alert=True)

    async def _finalize_submission(bot: AsyncTeleBot, message: Message, telegram_id: int, description: str):
        log_msg(f"[photo_handler] Finalizing submission for {telegram_id}, description_len={len(description)}")
        file_ids = _pending_photos.pop(telegram_id, [])
        _submit_progress_counts.pop(telegram_id, None)
        if not file_ids:
            log_msg(f"[photo_handler] No photo found in pending for {telegram_id}")
            await bot.send_message(message.chat.id, "⚠️ Сначала отправьте фото.")
            return

        log_msg(f"[photo_handler] Found {len(file_ids)} pending photo(s), calling RequestService.submit_product_request()")
        await bot.send_message(message.chat.id, f"⏳ Отправляем {len(file_ids)} фото на оценку...")

        repo = BotRepository()
        svc = RequestService(bot, repo)
        await svc.submit_product_request(
            chat_id=message.chat.id,
            telegram_id=telegram_id,
            file_ids=file_ids,
            description=description,
        )

    # Expose _finalize_submission so text_handler can call it
    register_photo_handler._finalize = _finalize_submission
    register_photo_handler._pending = _pending_photos
    register_photo_handler._submit_prompts = _submit_prompt_messages

