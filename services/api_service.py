# services/api_service.py — Handles ALL communication with the PHP backend (async).
# No business logic. No Telegram code. Just HTTP.
import asyncio
import hmac
import hashlib
import time
import aiohttp
from config import Config
from utils.retry import async_with_retry
from utils.logger import log_msg


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
        # FIX: single shared session instead of one per request
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
        log_msg(f"[api] Creating product request at {url}")
        log_msg(f"[api] telegram_id={telegram_id}, photo_count={len(images)}")

        body_for_sig = f"telegram_id={telegram_id}&description={description}"

        form = aiohttp.FormData()
        form.add_field("telegram_id", str(telegram_id))
        form.add_field("description", description)

        for index, (image_bytes, filename) in enumerate(images):
            log_msg(f"[api] photo#{index + 1} filename={filename}, image_size={len(image_bytes)} bytes")
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
                log_msg(f"[api] Response status: {response.status}")
                text = await response.text()
                log_msg(f"[api] Response body: {text[:500]}")

                if response.status not in (200, 201):
                    log_msg(f"[api] HTTP error: {response.status}", level="ERROR")
                    return None

                payload = await response.json(content_type=None)
                if payload.get("success") and "request_id" in payload:
                    log_msg(f"[api] Success! Got request_id={payload['request_id']}")
                    return {"request_id": int(payload["request_id"])}

                log_msg(f"[api] Unexpected response: {payload}", level="ERROR")
                return None

        except asyncio.TimeoutError as e:
            log_msg(f"[api] Timeout error: {e}", level="ERROR")
        except aiohttp.ClientError as e:
            log_msg(f"[api] Connection error: {e}", level="ERROR")
        except Exception as e:
            log_msg(f"[api] Request error: {e}", level="ERROR")

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
        log_msg(f"[api] Getting request status at {url}")

        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._auth_headers(""),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                log_msg(f"[api] Status response: {response.status}")
                if response.status != 200:
                    log_msg(f"[api] HTTP error: {response.status}", level="ERROR")
                    return None
                return await response.json(content_type=None)
        except Exception as e:
            log_msg(f"[api] Failed to get request status: {e}", level="ERROR")

        return None

    @async_with_retry()
    async def create_access_token(self, request_id: int, token: str) -> dict | None:
        """
        POST /api/bot/access-token
        """
        url = self._request_url_candidates("/bot/access-token")
        log_msg(f"[api] Creating access token for request {request_id}")

        body_for_sig = f"request_id={request_id}&token={token}"
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
                log_msg(f"[api] Token response status: {response.status}")
                if response.status not in (200, 201):
                    log_msg(f"[api] HTTP error: {response.status}", level="ERROR")
                    return None
                result = await response.json(content_type=None)
                log_msg(f"[api] Token created successfully")
                return result
        except Exception as e:
            log_msg(f"[api] Failed to create access token: {e}", level="ERROR")

        return None

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

    def _request_url_candidates(self, suffix: str):
        base = self.BASE.rstrip("/")
        return f"{base}/api{suffix}"