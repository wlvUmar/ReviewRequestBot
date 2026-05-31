import asyncio
import traceback
import secrets
import string
import html
import re
from config import Config
from db.repository import BotRepository
from services.api_service import ApiService
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from utils.logger import get_logger

logger = get_logger(__name__)

class RequestService:
    def __init__(self, bot: AsyncTeleBot, repo: BotRepository):
        self.bot = bot
        self.repo = repo
        self.api = ApiService()

 
    async def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        await self.repo.upsert_user(telegram_id, username, first_name)

    # -------------------------------------------------------------------------
    # Core submission flow
    # -------------------------------------------------------------------------
    async def submit_product_request(
        self,
        chat_id: int,
        telegram_id: int,
        file_ids: list[str],
        description: str,
    ) -> None:
        logger.debug(f"[submit] Starting submission for telegram_id={telegram_id}")
        
        logger.debug(f"[submit] Downloading {len(file_ids)} image(s) from Telegram")
        images = await self._download_images(file_ids)
        if not images:
            logger.warning(f"[submit] Failed to download any images")
            await self.bot.send_message(chat_id, "❌ Не удалось загрузить фото. Попробуйте ещё раз.")
            return

        logger.debug(f"[submit] Downloaded {len(images)} image(s)")

        logger.debug(f"[submit] Calling PHP API to create product request...")
        result = await self.api.create_product_request(
            telegram_id=telegram_id,
            description=description,
            images=images,
        )

        if result is None:
            logger.warning(f"[submit] API returned None - connection or parsing failed")
            await self.bot.send_message(
                chat_id,
                "❌ Не удалось отправить фото. Попробуйте ещё раз через пару минут."
            )
            return

        request_id: int = result["request_id"]
        logger.debug(f"[submit] API returned request_id={request_id}")

        # 3. Persist mapping: request_id ↔ telegram_id (so callback server can notify user)
        logger.debug(f"[submit] Saving request mapping...")
        await self.repo.save_request(
            request_id=request_id,
            telegram_id=telegram_id,
            file_id=file_ids[0],
            description=description,
        )
        logger.debug(f"[submit] Request mapping saved")
        
        logger.debug(f"[submit] Notifying admins...")
        preview_file_id = file_ids[0] if file_ids else None
        await self._notify_admins(telegram_id, request_id, len(file_ids), description, preview_file_id=preview_file_id)

        await self.bot.send_message(
            chat_id,
            f"✅ Фото отправлены.\n\n"
            "Скоро пришлём оценку сюда."
        )

    # -------------------------------------------------------------------------
    # Notification (called by callback server when PHP posts a review result)
    # -------------------------------------------------------------------------
    async def notify_review_result(self, request_id: int, status: str, price: str, notes: str, contact_phone: str = "") -> bool:
        logger.debug(f"[notify] request_id={request_id} status={status} price={price} contact_phone={contact_phone or 'EMPTY'}")
        mapping = await self.repo.get_request(request_id)
        if not mapping:
            logger.warning(f"[notify] mapping not found for request_id={request_id}")
            return False

        claim = await self.repo.claim_request_notification(request_id)
        if not claim:
            current_state = mapping.get("notification_sent")
            logger.warning(f"[notify] claim failed for request_id={request_id} state={current_state}")
            return current_state in (1, 2)

        if not claim.get("claimed"):
            current_state = claim.get("mapping", {}).get("notification_sent")
            logger.warning(f"[notify] claim already handled request_id={request_id} state={current_state}")
            return current_state in (1, 2)

        telegram_id = mapping["telegram_id"]
        text = ""

        if status == "approved" and price:
            text = f"💰 <b>Оценка:</b> {price}"
            if contact_phone:
                text += f"\n📞 <b>Контакт:</b> {contact_phone}"
            else:
                logger.info(f"[notify] contact phone empty for request_id={request_id}")
            if notes:
                text += f"\n📝 <b>Комментарий:</b> {notes}"
        else:
            text = "Спасибо! Фото получили. Сейчас не можем дать точную оценку."
            if notes:
                text += f"\n📝 <b>Комментарий:</b> {notes}"
            logger.debug(f"[notify] non-approved or empty price for request_id={request_id}")

        try:
            await self.bot.send_message(telegram_id, text)
            await self.repo.mark_request_notified(request_id)
            logger.debug(f"[notify] sent successfully for request_id={request_id}")
            return True
        except Exception as e:
            logger.error(f"[notify] Exception for request_id={request_id}: {e}", exc_info=True)
            await self.repo.release_request_notification(request_id)
            return False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    async def _download_images(self, file_ids: list[str]) -> list[tuple[bytes, str]]:
        results = await asyncio.gather(*[self._download_image(fid) for fid in file_ids])
        return [(b, f) for b, f in results if b is not None]

    async def _download_image(self, file_id: str) -> tuple[bytes | None, str]:
        try:
            logger.debug(f"[image] Downloading from Telegram API...")
            file_info = await self.bot.get_file(file_id)
            logger.debug(f"[image] File info: path={file_info.file_path}")
            downloaded = await self.bot.download_file(file_info.file_path)
            filename = file_info.file_path.split("/")[-1]  # e.g. photos/file_123.jpg
            size_mb = len(downloaded) / (1024 * 1024)
            logger.debug(f"[image] Downloaded {filename}: {size_mb:.2f} MB")
            if size_mb > Config.IMAGE_MAX_MB:
                logger.debug(f"[image] Image too large ({size_mb:.2f}MB > {Config.IMAGE_MAX_MB}MB)")
                return None, ""
            return downloaded, filename
        except Exception as e:
            logger.error(f"[image] Error downloading: {e}", exc_info=True)
            return None, ""
    

    async def _notify_admins(self, telegram_id: int, request_id: int, photo_count: int, description: str, preview_file_id: str | None = None) -> None:
        admin_ids = list(Config.ADMIN_IDS)
        if not admin_ids:
            logger.warning("notify_admins: no admin IDs configured")
            return

        directive_match = re.search(r"#([A-Za-z0-9_]+)=([0-9]{5,15})", description or "")
        if directive_match:
            try:
                target_id = int(directive_match.group(2))
                if target_id in admin_ids:
                    admin_ids = [target_id]
            except Exception:
                pass

        token = self._generate_access_token()
        await self._store_access_token(request_id, token)

        base_url = Config.PHP_API_BASE_URL.rstrip("/")
        access_link = f"{base_url}/admin/requests/{request_id}?token={token}"
        clean_desc = re.sub(r"#([A-Za-z0-9_]+)=[0-9]{5,15}", "", description or "").strip()
        safe_desc = html.escape(clean_desc)[:200]
        caption = (
            f"🔔 <b>Новый запрос</b>\n\n"
            f"📋 ID: <code>{request_id}</code>\n"
            f"👤 Telegram: <code>{telegram_id}</code>\n"
            f"📸 Фото: {photo_count}\n"
            f"📝 Описание: {safe_desc}"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Открыть запрос", web_app=WebAppInfo(url=access_link)))

        await asyncio.gather(
            *[self._send_admin_notification(aid, caption, markup, preview_file_id) for aid in admin_ids],
            return_exceptions=True,
        )




    async def _send_admin_notification(self, admin_id: int, message: str, markup: InlineKeyboardMarkup, preview_file_id: str | None = None) -> None:
        try:
            if preview_file_id:
                await self.bot.send_photo(admin_id, preview_file_id, caption=message, parse_mode="HTML", reply_markup=markup)
            else:
                await self.bot.send_message(admin_id, message, parse_mode="HTML", reply_markup=markup)
            logger.debug(f"[admin_notify] Sent notification to admin {admin_id}")
        except Exception as e:
            logger.warning(f"[admin_notify] Failed to notify admin {admin_id}: {e}")
    
    def _generate_access_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def _store_access_token(self, request_id: int, token: str) -> None:
        """Store access token in DB with 3-day expiration"""
        try:
            logger.debug(f"[admin_notify] Storing access token for request {request_id}, token={token[:16]}...")
            result = await self.api.create_access_token(request_id, token)
            if result:
                logger.debug(f"[admin_notify] Access token stored successfully for request {request_id}")
            else:
                logger.debug(f"[admin_notify] Failed to store access token for request {request_id} (API returned None)")
        except Exception as e:
            logger.error(f"[admin_notify] Error storing access token: {e}", exc_info=True)
