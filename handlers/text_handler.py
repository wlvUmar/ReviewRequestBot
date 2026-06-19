# handlers/text_handler.py — Captures description and price text after photo upload.
from telebot.async_telebot import AsyncTeleBot
from telebot.states.asyncio.context import StateContext
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.logger import get_logger
from utils.i18n import t
from utils.states import UserStates

logger = get_logger(__name__)


def register_text_handler(bot: AsyncTeleBot):

    # ========================================================================
    # AWAITING_DESCRIPTION: loop — accumulate text, show progress + Next btn
    # ========================================================================
    @bot.message_handler(content_types=["text"], state=UserStates.awaiting_description)
    async def handle_description_input(message: Message, state: StateContext):
        telegram_id = message.from_user.id
        chat_id = message.chat.id

        async with state.data() as data:
            lang = data.get("lang", "ru")
            pending = data.get("photos", [])

            if not pending:
                logger.debug(f"No pending photos for user_id={telegram_id}, rejecting description")
                await bot.send_message(chat_id, t(lang, "send_photo_first"))
                return

            new_text = message.text.strip()
            previous = (data.get("description") or "").strip()
            description = f"{previous}\n{new_text}".strip() if previous else new_text

            if len(description) > 2000:
                logger.warning(f"Description too long for user_id={telegram_id}: {len(description)} chars")
                await bot.send_message(chat_id, t(lang, "description_too_long"))
                return

            data["description"] = description
            chars = len(description)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t(lang, "next_button"), callback_data="confirm_description"))

        await bot.send_message(
            chat_id,
            t(lang, "description_progress", chars=chars, next=t(lang, "next_button")),
            parse_mode="HTML",
            reply_markup=markup,
        )
        logger.info(f"Description updated for user_id={telegram_id}: {chars} chars")

    # ========================================================================
    # confirm_description callback → move to price
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data == "confirm_description")
    async def handle_confirm_description(call: CallbackQuery, state: StateContext):
        telegram_id = call.from_user.id
        chat_id = call.message.chat.id

        async with state.data() as data:
            lang = data.get("lang", "ru")
            description = data.get("description", "")

        if not description.strip():
            await bot.answer_callback_query(call.id, t(lang, "description_prompt"))
            return

        await bot.answer_callback_query(call.id)
        await state.set(UserStates.awaiting_price)
        await bot.send_message(chat_id, t(lang, "price_prompt"))
        logger.info(f"Description confirmed for user_id={telegram_id}, moving to price")

    # ========================================================================
    # AWAITING_PRICE: parse price → show preview once with submit btn
    # ========================================================================
    @bot.message_handler(content_types=["text"], state=UserStates.awaiting_price)
    async def handle_price_input(message: Message, state: StateContext):
        import html as html_module
        telegram_id = message.from_user.id
        chat_id = message.chat.id

        async with state.data() as data:
            lang = data.get("lang", "ru")
            raw_price = message.text.strip()

        from utils.currency import parse_price
        try:
            price = parse_price(raw_price)
            logger.debug(f"Parsed price for user_id={telegram_id}: {price}")
        except ValueError:
            await bot.send_message(chat_id, t(lang, "price_invalid"))
            return

        async with state.data() as data:
            data["desired_price"] = price
            description = (data.get("description") or "").strip()
            pending = data.get("photos", [])
            caption_extra = (data.get("caption") or "").strip()

        if not pending:
            await bot.send_message(chat_id, t(lang, "send_photo_first"))
            return

        # Build preview caption
        full_desc = "\n".join(filter(None, [caption_extra, description]))
        safe_desc = html_module.escape(full_desc)
        safe_price = html_module.escape(price)
        price_line = f"\n<b>{t(lang, 'desired_price_label')}:</b> {safe_price}" if price else ""
        more = len(pending) - 1
        extra = f"\n\n{t(lang, 'preview_more_photos', more=more)}" if more > 0 else ""

        caption = (
            safe_desc
            + price_line
            + extra
            + "\n\n"
            + t(lang, "preview_note", submit=t(lang, "submit_button"))
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t(lang, "submit_button"), callback_data="confirm_send"))

        await state.set(UserStates.submitting)  # prevent further input during preview
        try:
            await bot.send_photo(
                chat_id,
                pending[0],
                caption=caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Preview send failed for user_id={telegram_id}: {e}")
            await bot.send_message(
                chat_id,
                t(lang, "preview_note", submit=t(lang, "submit_button")),
                reply_markup=markup,
            )
        # Reset to awaiting_photo after sending preview so confirm_send can finalize

    # ========================================================================
    # OTHER STATES: Redirect
    # ========================================================================
    @bot.message_handler(content_types=["text"], state="*")
    async def handle_text_wrong_state(message: Message, state: StateContext):
        telegram_id = message.from_user.id

        from config import Config
        if telegram_id in Config.ADMIN_IDS and not Config.DEBUG:
            return

        async with state.data() as data:
            lang = data.get("lang", "ru")

        await bot.send_message(message.chat.id, t(lang, "send_photo_first"))