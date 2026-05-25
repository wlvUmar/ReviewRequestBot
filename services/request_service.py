import io
import asyncio
import traceback
import secrets
import string
from config import Config
from db.repository import BotRepository
from services.api_service import ApiService
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.logger import log_msg

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
        log_msg(f"[submit] Starting submission for telegram_id={telegram_id}")
        
        # 1. Download image bytes from Telegram (concurrent)
        log_msg(f"[submit] Downloading {len(file_ids)} image(s) from Telegram")
        images = await self._download_images(file_ids)
        if not images:
            log_msg(f"[submit] Failed to download any images")
            await self.bot.send_message(chat_id, "❌ Не удалось загрузить фото. Попробуйте ещё раз.")
            return

        log_msg(f"[submit] Downloaded {len(images)} image(s)")

        # 2. POST to PHP backend — multipart upload
        log_msg(f"[submit] Calling PHP API to create product request...")
        result = await self.api.create_product_request(
            telegram_id=telegram_id,
            description=description,
            images=images,
        )

        if result is None:
            log_msg(f"[submit] API returned None - connection or parsing failed")
            await self.bot.send_message(
                chat_id,
                "❌ Не удалось отправить фото. Попробуйте ещё раз через пару минут."
            )
            return

        request_id: int = result["request_id"]
        log_msg(f"[submit] API returned request_id={request_id}")

        # 3. Persist mapping: request_id ↔ telegram_id (so callback server can notify user)
        log_msg(f"[submit] Saving request mapping...")
        await self.repo.save_request(
            request_id=request_id,
            telegram_id=telegram_id,
            file_id=file_ids[0],
            description=description,
        )
        log_msg(f"[submit] Request mapping saved")
        
        # 4. Notify admins
        log_msg(f"[submit] Notifying admins...")
        await self._notify_admins(telegram_id, request_id, len(file_ids), description)

        await self.bot.send_message(
            chat_id,
            f"✅ Фото отправлены.\n\n"
            "Скоро пришлём оценку сюда."
        )

    # -------------------------------------------------------------------------
    # Notification (called by callback server when PHP posts a review result)
    # -------------------------------------------------------------------------
    async def notify_review_result(self, request_id: int, status: str, price: str, notes: str, contact_phone: str = "") -> bool:
        log_msg(f"[notify] request_id={request_id} status={status} price={price} contact_phone={contact_phone or 'EMPTY'}")
        mapping = await self.repo.get_request(request_id)
        if not mapping:
            log_msg(f"[notify] mapping not found for request_id={request_id}")
            return False

        if not await self.repo.claim_request_notification(request_id):
            current_state = mapping.get("notification_sent")
            log_msg(f"[notify] claim failed for request_id={request_id} state={current_state}")
            return current_state in (1, 2)

        telegram_id = mapping["telegram_id"]
        text = ""

        if status == "approved" and price:
            text = f"💰 <b>Оценка:</b> {price}"
            if contact_phone:
                text += f"\n📞 <b>Контакт:</b> {contact_phone}"
            else:
                log_msg(f"[notify] contact phone empty for request_id={request_id}")
            if notes:
                text += f"\n📝 <b>Комментарий:</b> {notes}"
        else:
            text = "Спасибо! Фото получили. Сейчас не можем дать точную оценку."
            if notes:
                text += f"\n📝 <b>Комментарий:</b> {notes}"
            log_msg(f"[notify] non-approved or empty price for request_id={request_id}")

        try:
            await self.bot.send_message(telegram_id, text)
            await self.repo.mark_request_notified(request_id)
            log_msg(f"[notify] sent successfully for request_id={request_id}")
            return True
        except Exception as e:
            log_msg(f"[notify] Exception for request_id={request_id}: {e}")
            log_msg(traceback.format_exc())
            await self.repo.release_request_notification(request_id)
            return False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    async def _download_images(self, file_ids: list[str]) -> list[tuple[bytes, str]]:
        # Download all images concurrently
        tasks = [self._download_image(file_id) for file_id in file_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        images = []
        for result in results:
            if isinstance(result, Exception):
                log_msg(f"[image] Error downloading image: {result}")
                continue
            image_bytes, filename = result
            if image_bytes is None:
                continue
            images.append((image_bytes, filename))
        return images

    async def _download_image(self, file_id: str) -> tuple[bytes | None, str]:
        try:
            log_msg(f"[image] Downloading from Telegram API...")
            file_info = await self.bot.get_file(file_id)
            log_msg(f"[image] File info: path={file_info.file_path}")
            downloaded = await self.bot.download_file(file_info.file_path)
            filename = file_info.file_path.split("/")[-1]  # e.g. photos/file_123.jpg
            size_mb = len(downloaded) / (1024 * 1024)
            log_msg(f"[image] Downloaded {filename}: {size_mb:.2f} MB")
            if size_mb > Config.IMAGE_MAX_MB:
                log_msg(f"[image] Image too large ({size_mb:.2f}MB > {Config.IMAGE_MAX_MB}MB)")
                return None, ""
            return downloaded, filename
        except Exception as e:
            log_msg(f"[image] Error downloading: {e}")
            return None, ""
    
    async def _notify_admins(self, telegram_id: int, request_id: int, photo_count: int, description: str) -> None:
        """Send notification to all admins about new request"""
        admin_ids = Config.ADMIN_IDS
        if not admin_ids:
            log_msg(f"[admin_notify] No admin IDs configured")
            return
        
        # Generate secure token
        token = self._generate_access_token()
        
        # Store token in DB (3 days expiration)
        await self._store_access_token(request_id, token)
        
        # Build link with token
        base_url = Config.PHP_API_BASE_URL.rstrip("/")
        access_link = f"{base_url}/admin/requests/{request_id}?token={token}"
        
        message = (
            f"🔔 <b>Новый запрос</b>\n\n"
            f"📋 ID: <code>{request_id}</code>\n"
            f"👤 Telegram: <code>{telegram_id}</code>\n"
            f"📸 Фото: {photo_count}\n"
            f"📝 Описание: {description[:100]}"
        )
        
        # Create inline keyboard with link button
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Открыть запрос", url=access_link))
        
        # Notify all admins concurrently
        tasks = []
        for admin_id in admin_ids:
            tasks.append(self._send_admin_notification(admin_id, message, markup))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_admin_notification(self, admin_id: int, message: str, markup: InlineKeyboardMarkup) -> None:
        try:
            await self.bot.send_message(admin_id, message, parse_mode="HTML", reply_markup=markup)
            log_msg(f"[admin_notify] Sent notification to admin {admin_id}")
        except Exception as e:
            log_msg(f"[admin_notify] Failed to notify admin {admin_id}: {e}")
    
    def _generate_access_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def _store_access_token(self, request_id: int, token: str) -> None:
        """Store access token in DB with 3-day expiration"""
        try:
            log_msg(f"[admin_notify] Storing access token for request {request_id}, token={token[:16]}...")
            # Use API to store token on PHP side
            result = await self.api.create_access_token(request_id, token)
            if result:
                log_msg(f"[admin_notify] Access token stored successfully for request {request_id}")
            else:
                log_msg(f"[admin_notify] Failed to store access token for request {request_id} (API returned None)")
        except Exception as e:
            log_msg(f"[admin_notify] Error storing access token: {e}")
            import traceback
            log_msg(f"[admin_notify] Traceback: {traceback.format_exc()}")

