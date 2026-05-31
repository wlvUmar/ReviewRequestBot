import asyncio
import hmac
import hashlib
import time
import aiohttp
from urllib.parse import urlencode
from config import Config
from utils.retry import async_with_retry
from utils.logger import get_logger

logger = get_logger(__name__)

class ApiService:
    """
    Communicates with the existing PHP MVC backend REST API (async).

    Authentication strategy:
        Every request carries two headers:
          X-Bot-Timestamp : Unix timestamp (seconds)
          X-Bot-Signature : HMAC-SHA256( SECRET + ":" + TIMESTAMP + ":" + BODY )

        The PHP backend verifies the signature and rejects requests older than 60 s.
        This prevents replay attacks without needing OAuth or session tokens.
    """

    BASE = Config.PHP_API_BASE_URL
    SECRET = Config.PHP_API_SECRET

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Call this on shutdown to cleanly close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    @async_with_retry()
    async def create_product_request(
        self,
        telegram_id: int,
        description: str,
        images: list[tuple[bytes, str]],
    ) -> dict | None:
        """
        POST /api/bot/requests
        Multipart: image file + JSON metadata.
        Expected PHP response (200):
        {
            "success": true,
            "request_id": 42
        }
        """
        url = self._request_url_candidates("/bot/requests")
        logger.debug(f"[api] Creating product request at {url}")
        logger.debug(f"[api] telegram_id={telegram_id}, photo_count={len(images)}")

        body_for_sig = self._signed_body([
            ("telegram_id", str(telegram_id)),
            ("description", description),
        ])

        form = aiohttp.FormData()
        form.add_field("telegram_id", str(telegram_id))
        form.add_field("description", description)

        for index, (image_bytes, filename) in enumerate(images):
            logger.debug(f"[api] photo#{index + 1} filename={filename}, image_size={len(image_bytes)} bytes")
            form.add_field("images[]", image_bytes, filename=filename, content_type="image/jpeg")

        headers = self._auth_headers(body_for_sig)

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=form,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                logger.debug(f"[api] Response status: {response.status}")
                text = await response.text()
                logger.debug(f"[api] Response body: {text[:500]}")

                if response.status not in (200, 201):
                    logger.error(f"[api] HTTP error: {response.status}")
                    return None

                payload = await response.json(content_type=None)
                if payload.get("success") and "request_id" in payload:
                    logger.debug(f"[api] Success! Got request_id={payload['request_id']}")
                    return {"request_id": int(payload["request_id"])}

                logger.error(f"[api] Unexpected response: {payload}")
                return None

        except asyncio.TimeoutError as e:
            logger.error(f"[api] Timeout error: {e}")
        except aiohttp.ClientError as e:
            logger.error(f"[api] Connection error: {e}")
        except Exception as e:
            logger.error(f"[api] Request error: {e}")

        return None

    @async_with_retry()
    async def get_request_status(self, request_id: int) -> dict | None:
        """
        GET /api/bot/requests/{id}

        Expected PHP response:
        {
            "request_id": 42,
            "status": "pending|approved|rejected",
            "price": "150.00",
            "admin_notes": "Good condition",
            "contact_phone": "+998..."
        }
        """
        url = self._request_url_candidates(f"/bot/requests/{request_id}")
        logger.debug(f"[api] Getting request status at {url}")

        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._auth_headers(""),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Status response: {response.status}")
                if response.status != 200:
                    logger.error(f"[api] HTTP error: {response.status}")
                    return None
                return await response.json(content_type=None)
        except Exception as e:
            logger.error(f"[api] Failed to get request status: {e}")

        return None

    @async_with_retry()
    async def create_access_token(self, request_id: int, token: str) -> dict | None:
        """
        POST /api/bot/access-token
        """
        url = self._request_url_candidates("/bot/access-token")
        logger.debug(f"[api] Creating access token for request {request_id}")

        body_for_sig = self._signed_body([
            ("request_id", str(request_id)),
            ("token", token),
        ])
        data = {
            "request_id": str(request_id),
            "token": token,
        }
        headers = self._auth_headers(body_for_sig)

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Token response status: {response.status}")
                if response.status not in (200, 201):
                    logger.error(f"[api] HTTP error: {response.status}")
                    return None
                result = await response.json(content_type=None)
                logger.debug(f"[api] Token created successfully")
                return result
        except Exception as e:
            logger.error(f"[api] Failed to create access token: {e}")

        return None

    @async_with_retry()
    async def upsert_user(self, telegram_id: int, username: str, first_name: str, last_name: str) -> dict | None:
        url = self._request_url_candidates("/bot/users")
        body_for_sig = self._signed_body([
            ("telegram_id", str(telegram_id)),
            ("username", username),
            ("first_name", first_name),
            ("last_name", last_name),
        ])
        data = {
            "telegram_id": str(telegram_id),
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
        }

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=self._auth_headers(body_for_sig),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Upsert user response: {response.status}")
                if response.status not in (200, 201):
                    return None
                payload = await response.json(content_type=None)
                return payload if payload.get("success") else None
        except Exception as e:
            logger.warning(f"[api] Failed to upsert user: {e}")
            return None

    @async_with_retry()
    async def get_user(self, telegram_id: int) -> dict | None:
        url = self._request_url_candidates(f"/bot/users/{telegram_id}")
        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._auth_headers(""),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Get user response: {response.status}")
                if response.status != 200:
                    return None
                payload = await response.json(content_type=None)
                return payload.get("user") if payload.get("success") else None
        except Exception as e:
            logger.warning(f"[api] Failed to get user: {e}")
            return None

    @async_with_retry()
    async def save_phone(self, telegram_id: int, phone: str) -> bool:
        url = self._request_url_candidates(f"/bot/users/{telegram_id}/phone")
        body_for_sig = self._signed_body([
            ("telegram_id", str(telegram_id)),
            ("phone", phone),
        ])
        data = {
            "phone": phone,
        }

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=self._auth_headers(body_for_sig),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Save phone response: {response.status}")
                if response.status not in (200, 201):
                    return False
                payload = await response.json(content_type=None)
                return bool(payload.get("success"))
        except Exception as e:
            logger.warning(f"[api] Failed to save phone: {e}")
            return False

    @async_with_retry()
    async def get_phone(self, telegram_id: int) -> str | None:
        url = self._request_url_candidates(f"/bot/users/{telegram_id}/phone")
        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._auth_headers(""),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Get phone response: {response.status}")
                if response.status != 200:
                    return None
                payload = await response.json(content_type=None)
                return payload.get("phone") if payload.get("success") else None
        except Exception as e:
            logger.warning(f"[api] Failed to get phone: {e}")
            return None

    @async_with_retry()
    async def save_request(self, request_id: int, telegram_id: int, file_id: str, description: str) -> dict | None:
        url = self._request_url_candidates("/bot/mappings")
        body_for_sig = self._signed_body([
            ("request_id", str(request_id)),
            ("telegram_id", str(telegram_id)),
            ("notification_sent", "0"),
        ])
        data = {
            "request_id": str(request_id),
            "telegram_id": str(telegram_id),
            "notification_sent": "0",
        }

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=self._auth_headers(body_for_sig),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Save mapping response: {response.status}")
                if response.status not in (200, 201):
                    return None
                payload = await response.json(content_type=None)
                return payload if payload.get("success") else None
        except Exception as e:
            logger.warning(f"[api] Failed to save mapping: {e}")
            return None

    @async_with_retry()
    async def get_request(self, request_id: int) -> dict | None:
        url = self._request_url_candidates(f"/bot/mappings/{request_id}")
        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._auth_headers(""),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Get mapping response: {response.status}")
                if response.status != 200:
                    return None
                payload = await response.json(content_type=None)
                return payload.get("mapping") if payload.get("success") else None
        except Exception as e:
            logger.warning(f"[api] Failed to get mapping: {e}")
            return None

    @async_with_retry()
    async def mark_request_notified(self, request_id: int) -> dict | None:
        url = self._request_url_candidates(f"/bot/mappings/{request_id}/notified")
        body_for_sig = self._signed_body([("request_id", str(request_id))])
        data = {"request_id": str(request_id)}

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=self._auth_headers(body_for_sig),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Mark notified response: {response.status}")
                if response.status not in (200, 201):
                    return None
                return await response.json(content_type=None)
        except Exception as e:
            logger.warning(f"[api] Failed to mark notified: {e}")
            return None

    @async_with_retry()
    async def claim_request_notification(self, request_id: int) -> dict | None:
        url = self._request_url_candidates(f"/bot/mappings/{request_id}/claim")
        body_for_sig = self._signed_body([("request_id", str(request_id))])
        data = {"request_id": str(request_id)}

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=self._auth_headers(body_for_sig),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Claim response: {response.status}")
                if response.status not in (200, 201):
                    return None
                payload = await response.json(content_type=None)
                return payload if payload.get("success") else None
        except Exception as e:
            logger.warning(f"[api] Failed to claim notification: {e}")
            return None

    @async_with_retry()
    async def release_request_notification(self, request_id: int) -> dict | None:
        url = self._request_url_candidates(f"/bot/mappings/{request_id}/release")
        body_for_sig = self._signed_body([("request_id", str(request_id))])
        data = {"request_id": str(request_id)}

        try:
            session = await self._get_session()
            async with session.post(
                url,
                data=data,
                headers=self._auth_headers(body_for_sig),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Release response: {response.status}")
                if response.status not in (200, 201):
                    return None
                return await response.json(content_type=None)
        except Exception as e:
            logger.warning(f"[api] Failed to release notification: {e}")
            return None

    @async_with_retry()
    async def get_pending_unnotified(self) -> list[dict]:
        url = self._request_url_candidates("/bot/mappings")
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params={"notification_sent": "0"},
                headers=self._auth_headers(""),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                logger.debug(f"[api] Pending mappings response: {response.status}")
                if response.status != 200:
                    return []
                payload = await response.json(content_type=None)
                return payload.get("mappings", []) if payload.get("success") else []
        except Exception as e:
            logger.warning(f"[api] Failed to get pending mappings: {e}")
            return []

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _auth_headers(self, body: str) -> dict:
        timestamp = str(int(time.time()))
        message = f"{self.SECRET}:{timestamp}:{body}"
        signature = hmac.new(
            self.SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Bot-Timestamp": timestamp,
            "X-Bot-Signature": signature,
        }

    def _signed_body(self, fields: list[tuple[str, str]]) -> str:
        return urlencode(fields, doseq=False)

    def _request_url_candidates(self, suffix: str):
        base = self.BASE.rstrip("/")
        return f"{base}/api{suffix}"


