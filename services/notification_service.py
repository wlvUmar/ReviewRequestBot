import asyncio
from config import Config
from db.repository import BotRepository
from services.api_service import ApiService
from services.request_service import RequestService
from utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Background poller that reconciles request statuses and notifies users (async).
    Use this if the PHP backend cannot reliably POST webhooks to the bot.
    """

    def __init__(self, bot, interval: int | None = None):
        self.bot = bot
        self.interval = interval or Config.NOTIFY_POLL_INTERVAL
        self.repo = BotRepository()
        self.api = ApiService()
        self.req_svc = RequestService(self.bot, self.repo)  # Create once, reuse per poll
        self._stop = asyncio.Event()

    def stop(self):
        self._stop.set()

    async def run(self):
        while not self._stop.is_set():
            try:
                pending = await self.repo.get_pending_unnotified()
                for mapping in pending:
                    req_id = mapping.get("request_id")
                    if not req_id:
                        continue
                    # Ask PHP for current status
                    status_payload = await self.api.get_request_status(int(req_id))
                    if not status_payload:
                        continue
                    status = status_payload.get("status")
                    if status in ("approved", "rejected"):
                        # Use the pre-created RequestService instance
                        result = await self.req_svc.notify_review_result(
                            int(req_id),
                            status,
                            status_payload.get("price", ""),
                            status_payload.get("admin_notes") or status_payload.get("notes", ""),
                            status_payload.get("contact_phone", "")
                        )
                        logger.info(
                            "[notifier] notify_review_result request_id=%s result=%s",
                            req_id,
                            result,
                        )
            except Exception as e:
                logger.exception("[notifier] error: %s", e)
            # Sleep until next poll
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
