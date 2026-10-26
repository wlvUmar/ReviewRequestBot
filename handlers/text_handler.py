# handlers/text_handler.py — description + price steps, preview, and the catch-alls.
import html as html_module

from telebot.async_telebot import AsyncTeleBot
from telebot.states.asyncio.context import StateContext
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from utils.flow import is_ignored_admin, state_is
from utils.logger import get_logger
from utils.i18n import t
from utils.states import UserStates

logger = get_logger(__name__)

PREVIEW_DESC_LIMIT = 600  # a photo caption is capped at 1024 chars by Telegram


def _cancel_button(lang: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="cancel_flow")


def register_text_handler(bot: AsyncTeleBot):

    # ========================================================================
    # Preview (shared by the typed price and the "don't know" button)
    # ========================================================================
    async def _show_preview(chat_id: int, state: StateContext, telegram_id: int) -> None:
        async with state.data() as data:
            lang = data.get("lang", "ru")
            price = str(data.get("desired_price") or "0")
            description = (data.get("description") or "").strip()
            caption_extra = (data.get("caption") or "").strip()
            pending = data.get("photos", [])

        if not pending:
            await bot.send_message(chat_id, t(lang, "send_photo_first"))
            return

        full_desc = "\n".join(filter(None, [caption_extra, description]))
        if len(full_desc) > PREVIEW_DESC_LIMIT:
            full_desc = full_desc[:PREVIEW_DESC_LIMIT].rstrip() + "…"
        safe_desc = html_module.escape(full_desc)
        price_text = t(lang, "price_not_set") if price.strip() in ("", "0") else html_module.escape(price)
        more = len(pending) - 1
        extra = f"\n{t(lang, 'preview_more_photos', more=more)}" if more > 0 else ""

        caption = (
            f"{t(lang, 'preview_title')}\n\n"
            f"{safe_desc}\n\n"
            f"<b>{t(lang, 'desired_price_label')}:</b> {price_text}"
            f"{extra}\n\n"
            f"{t(lang, 'preview_note', submit=t(lang, 'submit_button'))}"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t(lang, "submit_button"), callback_data="confirm_send"))
        markup.add(
            InlineKeyboardButton(t(lang, "btn_edit"), callback_data="edit_request"),
            _cancel_button(lang),
        )

        await state.set(UserStates.submitting)  # free text is not an input here; use the buttons
        try:
            await bot.send_photo(chat_id, pending[0], caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Preview send failed for user_id={telegram_id}: {e}")
            await bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="HTML")

    # ========================================================================
    # AWAITING_DESCRIPTION: accumulate text, show progress + Next btn
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
        markup.add(_cancel_button(lang))

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
            description = (data.get("description") or "").strip()
            caption = (data.get("caption") or "").strip()

        # A caption written under the photo counts as the description.
        if not description and not caption:
            await bot.answer_callback_query(call.id, t(lang, "description_prompt"))
            return

        await bot.answer_callback_query(call.id)
        await state.set(UserStates.awaiting_price)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t(lang, "btn_price_skip"), callback_data="price_skip"))
        markup.add(_cancel_button(lang))
        await bot.send_message(chat_id, t(lang, "price_prompt"), parse_mode="HTML", reply_markup=markup)
        logger.info(f"Description confirmed for user_id={telegram_id}, moving to price")

    # ========================================================================
    # AWAITING_PRICE: typed price OR the "don't know" button → preview
    # ========================================================================
    @bot.message_handler(content_types=["text"], state=UserStates.awaiting_price)
    async def handle_price_input(message: Message, state: StateContext):
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
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(t(lang, "btn_price_skip"), callback_data="price_skip"))
            await bot.send_message(chat_id, t(lang, "price_invalid"), reply_markup=markup)
            return

        async with state.data() as data:
            data["desired_price"] = price

        await _show_preview(chat_id, state, telegram_id)

    @bot.callback_query_handler(func=lambda call: call.data == "price_skip", state=UserStates.awaiting_price)
    async def handle_price_skip(call: CallbackQuery, state: StateContext):
        async with state.data() as data:
            data["desired_price"] = "0"
        await bot.answer_callback_query(call.id)
        try:
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        await _show_preview(call.message.chat.id, state, call.from_user.id)

    # ========================================================================
    # "Edit" on the preview → back to the description step, photos are kept
    # ========================================================================
    @bot.callback_query_handler(func=lambda call: call.data == "edit_request")
    async def handle_edit_request(call: CallbackQuery, state: StateContext):
        async with state.data() as data:
            lang = data.get("lang", "ru")
            has_photos = bool(data.get("photos"))
            data.pop("description", None)
            data.pop("desired_price", None)
            data.pop("caption", None)
        await bot.answer_callback_query(call.id)
        try:
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        if not has_photos:
            await bot.send_message(call.message.chat.id, t(lang, "send_photo_first"))
            return
        await state.set(UserStates.awaiting_description)
        markup = InlineKeyboardMarkup()
        markup.add(_cancel_button(lang))
        await bot.send_message(call.message.chat.id, t(lang, "edit_prompt"), reply_markup=markup)

    # ========================================================================
    # OTHER STATES: say what is expected right now, not just "send a photo"
    # ========================================================================
    @bot.message_handler(content_types=["text"], state="*")
    async def handle_text_wrong_state(message: Message, state: StateContext):
        if is_ignored_admin(message.from_user.id):
            return

        current = await state.get()
        async with state.data() as data:
            lang = data.get("lang", "ru")

        if not current:
            text = t(lang, "use_start_first")
        elif state_is(current, "submitting"):
            text = t(lang, "wrong_state_preview", submit=t(lang, "submit_button"))
        elif state_is(current, "awaiting_lang"):
            text = t(lang, "choose_language")
        else:
            text = t(lang, "wrong_state_photo")
        await bot.send_message(message.chat.id, text)

    @bot.message_handler(content_types=["photo"], state="*")
    async def handle_photo_wrong_state(message: Message, state: StateContext):
        """Photos that arrive while the bot expects something else (price, preview, phone...)."""
        if is_ignored_admin(message.from_user.id):
            return

        current = await state.get()
        async with state.data() as data:
            lang = data.get("lang", "ru")

        if not current:
            text = t(lang, "use_start_first")
        elif state_is(current, "submitting"):
            text = t(lang, "wrong_state_preview", submit=t(lang, "submit_button"))
        elif state_is(current, "awaiting_price"):
            text = t(lang, "price_prompt")
        elif state_is(current, "awaiting_phone"):
            text = t(lang, "phone_prompt")
        elif state_is(current, "awaiting_lang"):
            text = t(lang, "choose_language")
        else:
            text = t(lang, "wrong_state_photo")
        await bot.send_message(message.chat.id, text, parse_mode="HTML")

    # ========================================================================
    # LAST RESORT: users with no stored state (never pressed /start, or the state
    # expired). telebot's state="*" does not match "no state", so without this the
    # bot would look dead to them.
    # ========================================================================
    @bot.message_handler(content_types=["text", "photo"])
    async def handle_no_state(message: Message, state: StateContext):
        if is_ignored_admin(message.from_user.id):
            return
        async with state.data() as data:
            lang = data.get("lang", "ru")
        await bot.send_message(message.chat.id, t(lang, "use_start_first"))
