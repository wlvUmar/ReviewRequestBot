# db/repository.py — Bot storage now goes through the PHP backend API.
from services.api_service import ApiService
from utils.logger import log_msg


class BotRepository:
    def __init__(self):
        self.api = ApiService()

    async def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        await self.api.upsert_user(telegram_id, username, first_name, "")

    async def get_user(self, telegram_id: int) -> dict | None:
        return await self.api.get_user(telegram_id)

    async def save_phone(self, telegram_id: int, phone: str) -> None:
        await self.api.save_phone(telegram_id, phone)

    async def get_phone(self, telegram_id: int) -> str | None:
        return await self.api.get_phone(telegram_id)

    async def save_request(
        self,
        request_id: int,
        telegram_id: int,
        file_id: str,
        description: str,
    ) -> None:
        """Store the mapping between a PHP request_id and a Telegram user."""
        await self.api.save_request(request_id, telegram_id, file_id, description)

    async def get_request(self, request_id: int) -> dict | None:
        return await self.api.get_request(request_id)

    async def mark_request_notified(self, request_id: int) -> None:
        await self.api.mark_request_notified(request_id)

    async def claim_request_notification(self, request_id: int) -> dict | None:
        payload = await self.api.claim_request_notification(request_id)
        if not payload:
            log_msg(f"[repo] claim missing request_id={request_id}")
            return None

        mapping = payload.get("mapping", {})
        state = mapping.get("notification_sent")
        if payload.get("claimed"):
            log_msg(f"[repo] claim acquired request_id={request_id}")
            return payload

        log_msg(f"[repo] claim already handled request_id={request_id} state={state}")
        return payload

    async def release_request_notification(self, request_id: int) -> None:
        await self.api.release_request_notification(request_id)

    async def get_pending_unnotified(self) -> list[dict]:
        return await self.api.get_pending_unnotified()
