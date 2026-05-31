# handlers/text_handler.py — Captures description text that follows a photo upload (async).
import asyncio
import html
import traceback
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils.logger import get_logger
from utils.i18n import t


logger = get_logger(__name__)

def register_text_handler(bot: AsyncTeleBot):
    async def _get_data(chat_id: int, user_id: int) -> dict:
        res = bot.current_states.get_data(chat_id, user_id)#type:ignore
        if asyncio.iscoroutine(res):
            res = await res
        return res or {}

    async def _get_state(chat_id: int, user_id: int):
        res = bot.get_state(user_id, chat_id=chat_id)
        if asyncio.iscoroutine(res):
            res = await res
        return res

    async def _update_data(chat_id: int, user_id: int, updates: dict) -> None:
        # merge updates into existing data and persist
        res = bot.current_states.get_data(chat_id, user_id)#type:ignore
        if asyncio.iscoroutine(res):
            res = await res
        data = res or {}
        data.update(updates)
        r = bot.current_states.reset_data(chat_id, user_id)#type:ignore
        if asyncio.iscoroutine(r):
            await r
        for k, v in data.items():
            s = bot.current_states.set_data(chat_id, user_id, k, v) #type:ignore
            if asyncio.iscoroutine(s):
                await s

    async def _set_state(chat_id: int, user_id: int, state: str):
        res = bot.set_state(user_id, state, chat_id=chat_id)
        if asyncio.iscoroutine(res):
            await res

    @bot.message_handler(func=lambda m: m.content_type == "text" and not m.text.startswith("/"))
    async def handle_text(message: Message):
        logger.debug(f"[text_handler] Text message from {message.from_user.id}: {str(message.text)[:50]}")
        telegram_id = message.from_user.id

        # Ignore admins — they should not participate in user flows (unless DEBUG enabled)
        if telegram_id in __import__('config').Config.ADMIN_IDS and not __import__('config').Config.DEBUG:
            logger.debug(f"[text_handler] Ignoring text from admin {telegram_id}")
            return

        data = await _get_data(message.chat.id, telegram_id)
        pending = data.get("pending_photos", [])
        lang = data.get("lang", "ru")

        state = await _get_state(message.chat.id, telegram_id)
        if state == "awaiting_price":
            raw_price = message.text.strip()  # type:ignore
            cleaned = raw_price.replace(" ", "").replace(",", "").replace(".", "")
            if not cleaned.isdigit() or int(cleaned) <= 0:
                await bot.send_message(message.chat.id, t(lang, "price_invalid"))
                return

            await _update_data(message.chat.id, telegram_id, {"desired_price": cleaned})
            await _set_state(message.chat.id, telegram_id, "awaiting_description")
            await bot.send_message(message.chat.id, t(lang, "price_saved"))
            await bot.send_message(message.chat.id, t(lang, "description_prompt"))
            return

        # enforce stateful flow: description is accepted only after photos were collected
        if state != "awaiting_description":
            logger.debug(f"[text_handler] Received text in state={state} from {telegram_id}, sending help")
            await bot.send_message(message.chat.id, t(lang, "send_photo_first"))
            return

        if pending:
            logger.debug(f"[text_handler] Found pending photos for {telegram_id}, treating as description (preview mode)")
            new_text = message.text.strip()  # type:ignore
            previous_description = (data.get("pending_description") or "").strip()
            description = f"{previous_description}\n{new_text}".strip() if previous_description else new_text
            if len(description) > 2000:
                await bot.send_message(message.chat.id, t(lang, "description_too_long"))
                return

            # save draft description
            data["pending_description"] = description

            # prepare preview caption
            first_file = pending[0]
            more = len(pending) - 1
            extra = ""
            if more > 0:
                extra = "\n\n" + t(lang, "preview_more_photos", more=more)

            safe_description = html.escape(description)
            desired_price = html.escape(str(data.get("desired_price", "")).strip())
            price_line = f"\n<b>цена:</b> {desired_price}" if desired_price else ""
            caption = safe_description + price_line + extra + "\n\n" + t(lang, "preview_note", submit=t(lang, "submit_button"))

            # build inline send button
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(t(lang, "submit_button"), callback_data="confirm_send"))

            # if preview exists, try to edit it, otherwise send new preview photo
            preview = data.get("preview")
            try:
                # wrap network calls with timeout so bot doesn't hang
                TIMEOUT = 12
                if preview:
                    logger.debug(f"[text_handler] Editing preview (msg={preview.get('message_id')}) for {telegram_id}")
                    await asyncio.wait_for(
                        bot.edit_message_caption(caption=caption, chat_id=preview["chat_id"], message_id=preview["message_id"], parse_mode="HTML", reply_markup=markup),
                        timeout=TIMEOUT,
                    )
                    logger.debug(f"[text_handler] Updated preview for {telegram_id}")
                else:
                    logger.debug(f"[text_handler] Sending new preview photo for {telegram_id} (file_id={first_file})")
                    sent = await asyncio.wait_for(
                        bot.send_photo(message.chat.id, first_file, caption=caption, reply_markup=markup, parse_mode="HTML"),
                        timeout=TIMEOUT,
                    )
                    data["preview"] = {"chat_id": sent.chat.id, "message_id": sent.message_id, "file_id": first_file}
                    logger.debug(f"[text_handler] Sent preview for {telegram_id} (msg={sent.message_id})")

                # persist pending_description and preview info
                await _update_data(message.chat.id, telegram_id, {"pending_description": description, "preview": data.get("preview")})

                # stay in awaiting_description so more text updates preview; user must press Send
                await _set_state(message.chat.id, telegram_id, "awaiting_description")
            except asyncio.TimeoutError:
                logger.debug(f"[text_handler] Preview send/edit timeout for {telegram_id}")
                await _update_data(message.chat.id, telegram_id, {"pending_description": description})
                try:
                    await bot.send_message(message.chat.id, t(lang, "preview_note", submit=t(lang, "submit_button")))
                except Exception as e:
                    logger.error(f"[text_handler] Fallback send_message also failed: {e}")
            except Exception as e:
                logger.warning(f"[text_handler] Failed to send/edit preview for {telegram_id}: {e}\n{traceback.format_exc()}")
                # fallback: just notify user that description was saved
                await _update_data(message.chat.id, telegram_id, {"pending_description": description})
                try:
                    await bot.send_message(message.chat.id, t(lang, "preview_note", submit=t(lang, "submit_button")))
                except Exception as e2:
                    logger.warning(f"[text_handler] Fallback send_message failed: {e2}")
        else:
            logger.debug(f"[text_handler] No pending photo for {telegram_id}, sending help message")
            await bot.send_message(
                message.chat.id,
                t(lang, "send_photo_first")
            )
