# handlers/text_handler.py — Captures description and price text after photo upload.
import asyncio
import html
import traceback
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils.logger import get_logger
from utils.i18n import t
from utils.currency import parse_price_to_uzs

logger = get_logger(__name__)


def register_text_handler(bot: AsyncTeleBot):
    async def _get_data(chat_id: int, user_id: int) -> dict:
        res = bot.current_states.get_data(chat_id, user_id)  # type: ignore
        if asyncio.iscoroutine(res):
            res = await res
        return res or {}

    async def _get_state(chat_id: int, user_id: int):
        res = bot.get_state(user_id, chat_id=chat_id)
        if asyncio.iscoroutine(res):
            res = await res
        return res

    async def _update_data(chat_id: int, user_id: int, updates: dict) -> None:
        res = bot.current_states.get_data(chat_id, user_id)  # type: ignore
        if asyncio.iscoroutine(res):
            res = await res
        data = res or {}
        data.update(updates)
        r = bot.current_states.reset_data(chat_id, user_id)  # type: ignore
        if asyncio.iscoroutine(r):
            await r
        for k, v in data.items():
            s = bot.current_states.set_data(chat_id, user_id, k, v)  # type: ignore
            if asyncio.iscoroutine(s):
                await s

    async def _set_state(chat_id: int, user_id: int, state: str):
        res = bot.set_state(user_id, state, chat_id=chat_id)
        if asyncio.iscoroutine(res):
            await res

    @bot.message_handler(func=lambda m: m.content_type == "text" and not m.text.startswith("/"))
    async def handle_text(message: Message):
        logger.debug(
            f"[text_handler] Text from {message.from_user.id}: {str(message.text)[:50]}"
        )
        telegram_id = message.from_user.id

        if telegram_id in __import__("config").Config.ADMIN_IDS and not __import__("config").Config.DEBUG:
            logger.debug(f"[text_handler] Ignoring text from admin {telegram_id}")
            return

        data = await _get_data(message.chat.id, telegram_id)
        pending = data.get("pending_photos", [])
        lang = data.get("lang", "ru")
        state = await _get_state(message.chat.id, telegram_id)

        # ------------------------------------------------------------------
        # State: awaiting_price
        # ------------------------------------------------------------------
        if state == "awaiting_price":
            raw_price = message.text.strip()  # type: ignore
            try:
                uzs_amount, display = parse_price_to_uzs(raw_price)
            except ValueError:
                await bot.send_message(message.chat.id, t(lang, "price_invalid"))
                return

            # Store the normalized UZS integer and the human-readable display string
            await _update_data(message.chat.id, telegram_id, {
                "desired_price_uzs": uzs_amount,       # int, always UZS
                "desired_price_display": display,       # e.g. "800 000 UZS (≈$63)"
            })
            await _set_state(message.chat.id, telegram_id, "awaiting_description")
            await bot.send_message(message.chat.id, t(lang, "price_saved"))
            await bot.send_message(message.chat.id, t(lang, "description_prompt"))
            return

        # ------------------------------------------------------------------
        # Wrong state — not awaiting description
        # ------------------------------------------------------------------
        if state != "awaiting_description":
            logger.debug(
                f"[text_handler] Text in state={state} from {telegram_id}, sending help"
            )
            await bot.send_message(message.chat.id, t(lang, "send_photo_first"))
            return

        # ------------------------------------------------------------------
        # State: awaiting_description — build preview
        # ------------------------------------------------------------------
        if not pending:
            logger.debug(f"[text_handler] No pending photo for {telegram_id}")
            await bot.send_message(message.chat.id, t(lang, "send_photo_first"))
            return

        new_text = message.text.strip()  # type: ignore
        previous_description = (data.get("pending_description") or "").strip()
        description = (
            f"{previous_description}\n{new_text}".strip() if previous_description else new_text
        )
        if len(description) > 2000:
            await bot.send_message(message.chat.id, t(lang, "description_too_long"))
            return

        data["pending_description"] = description

        # Build preview caption
        first_file = pending[0]
        more = len(pending) - 1
        extra = f"\n\n{t(lang, 'preview_more_photos', more=more)}" if more > 0 else ""

        safe_description = html.escape(description)
        price_display = html.escape(data.get("desired_price_display", "").strip())
        price_line = f"\n<b>{t(lang, 'desired_price_label')}:</b> {price_display}" if price_display else ""
        caption = (
            safe_description
            + price_line
            + extra
            + "\n\n"
            + t(lang, "preview_note", submit=t(lang, "submit_button"))
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t(lang, "submit_button"), callback_data="confirm_send"))

        preview = data.get("preview")
        try:
            TIMEOUT = 12
            if preview:
                logger.debug(
                    f"[text_handler] Editing preview (msg={preview.get('message_id')}) "
                    f"for {telegram_id}"
                )
                await asyncio.wait_for(
                    bot.edit_message_caption(
                        caption=caption,
                        chat_id=preview["chat_id"],
                        message_id=preview["message_id"],
                        parse_mode="HTML",
                        reply_markup=markup,
                    ),
                    timeout=TIMEOUT,
                )
            else:
                logger.debug(
                    f"[text_handler] Sending new preview for {telegram_id} (file_id={first_file})"
                )
                sent = await asyncio.wait_for(
                    bot.send_photo(
                        message.chat.id,
                        first_file,
                        caption=caption,
                        reply_markup=markup,
                        parse_mode="HTML",
                    ),
                    timeout=TIMEOUT,
                )
                data["preview"] = {
                    "chat_id": sent.chat.id,
                    "message_id": sent.message_id,
                    "file_id": first_file,
                }

            await _update_data(
                message.chat.id,
                telegram_id,
                {"pending_description": description, "preview": data.get("preview")},
            )
            await _set_state(message.chat.id, telegram_id, "awaiting_description")

        except asyncio.TimeoutError:
            logger.debug(f"[text_handler] Preview timeout for {telegram_id}")
            await _update_data(
                message.chat.id, telegram_id, {"pending_description": description}
            )
            try:
                await bot.send_message(
                    message.chat.id,
                    t(lang, "preview_note", submit=t(lang, "submit_button")),
                )
            except Exception as e:
                logger.error(f"[text_handler] Fallback send_message failed: {e}")

        except Exception as e:
            logger.warning(
                f"[text_handler] Failed to send/edit preview for {telegram_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            await _update_data(
                message.chat.id, telegram_id, {"pending_description": description}
            )
            try:
                await bot.send_message(
                    message.chat.id,
                    t(lang, "preview_note", submit=t(lang, "submit_button")),
                )
            except Exception as e2:
                logger.warning(f"[text_handler] Fallback send_message failed: {e2}") 