# services/request_service.py — All business logic lives here, not in handlers.
import io
import telebot
from config import Config
from db.repository import BotRepository
from services.api_service import ApiService

class RequestService:
    def __init__(self, bot: telebot.TeleBot, repo: BotRepository):
        self.bot = bot
        self.repo = repo
        self.api = ApiService()

    # -------------------------------------------------------------------------
    # User management
    # -------------------------------------------------------------------------
    def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        self.repo.upsert_user(telegram_id, username, first_name)

    # -------------------------------------------------------------------------
    # Core submission flow
    # -------------------------------------------------------------------------
    def submit_product_request(
        self,
        chat_id: int,
        telegram_id: int,
        file_id: str,
        description: str,
    ) -> None:
        # 1. Download image bytes from Telegram
        image_bytes, filename = self._download_image(file_id)
        if image_bytes is None:
            self.bot.send_message(chat_id, "❌ Failed to download your photo. Please try again.")
            return

        # 2. POST to PHP backend — multipart upload
        result = self.api.create_product_request(
            telegram_id=telegram_id,
            description=description,
            image_bytes=image_bytes,
            filename=filename,
        )

        if result is None:
            self.bot.send_message(
                chat_id,
                "❌ Could not reach the review system. Your request was <b>not</b> submitted.\n"
                "Please try again in a few minutes."
            )
            return

        request_id: int = result["request_id"]

        # 3. Persist mapping: request_id ↔ telegram_id (so callback server can notify user)
        self.repo.save_request(
            request_id=request_id,
            telegram_id=telegram_id,
            file_id=file_id,
            description=description,
        )

        self.bot.send_message(
            chat_id,
            f"✅ <b>Request #{request_id} submitted!</b>\n\n"
            "An admin will review your photo shortly. "
            "I'll notify you here with the result."
        )

    # -------------------------------------------------------------------------
    # Notification (called by callback server when PHP posts a review result)
    # -------------------------------------------------------------------------
    def notify_review_result(self, request_id: int, status: str, price: str, notes: str) -> bool:
        mapping = self.repo.get_request(request_id)
        if not mapping:
            return False

        telegram_id = mapping["telegram_id"]

        if status == "approved":
            text = (
                f"🎉 <b>Request #{request_id} approved!</b>\n\n"
                f"💰 <b>Offered price:</b> {price}\n"
                f"📝 <b>Admin notes:</b> {notes or '—'}"
            )
        elif status == "rejected":
            text = (
                f"❌ <b>Request #{request_id} was not approved.</b>\n\n"
                f"📝 <b>Reason:</b> {notes or 'No reason provided.'}"
            )
        else:
            text = (
                f"ℹ️ <b>Request #{request_id} update:</b> {status}\n"
                f"📝 {notes or ''}"
            )

        try:
            self.bot.send_message(telegram_id, text)
            self.repo.mark_request_notified(request_id)
            return True
        except telebot.apihelper.ApiException as e:
            print(f"[notify] Failed to message user {telegram_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _download_image(self, file_id: str) -> tuple[bytes | None, str]:
        try:
            file_info = self.bot.get_file(file_id)
            downloaded = self.bot.download_file(file_info.file_path)
            filename = file_info.file_path.split("/")[-1]  # e.g. photos/file_123.jpg
            size_mb = len(downloaded) / (1024 * 1024)
            if size_mb > Config.IMAGE_MAX_MB:
                return None, ""
            return downloaded, filename
        except Exception as e:
            print(f"[image download] Error: {e}")
            return None, ""