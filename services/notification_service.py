import time
import threading
import traceback
from config import Config
from db.repository import BotRepository
from services.api_service import ApiService
from services.request_service import RequestService
from utils.logger import log_msg

 
class NotificationService:
    """Background poller that reconciles request statuses and notifies users.
    Use this if the PHP backend cannot reliably POST webhooks to the bot.
    """

    def __init__(self, bot, interval: int | None = None):
        self.bot = bot
        self.interval = interval or Config.NOTIFY_POLL_INTERVAL
        self.repo = BotRepository()
        self.api = ApiService()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                pending = self.repo.get_pending_unnotified()
                for mapping in pending:
                    req_id = mapping.get("request_id")
                    if not req_id:
                        continue
                    # Ask PHP for current status
                    status_payload = self.api.get_request_status(int(req_id))
                    if not status_payload:
                        continue
                    status = status_payload.get("status")
                    if status in ("approved", "rejected"):
                        # Use a RequestService instance to send notification and mark notified
                        svc = RequestService(self.bot, self.repo)
                        result = svc.notify_review_result(
                            int(req_id),
                            status,
                            status_payload.get("price", ""),
                            status_payload.get("admin_notes") or status_payload.get("notes", ""),
                            status_payload.get("contact_phone", "")
                        )
                        log_msg(f"[notifier] notify_review_result request_id={req_id} result={result}")
            except Exception as e:
                log_msg(f"[notifier] error: {e}")
                log_msg(traceback.format_exc())
            # Sleep until next poll
            time.sleep(self.interval)
