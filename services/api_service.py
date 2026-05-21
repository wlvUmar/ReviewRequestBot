# services/api_service.py — Handles ALL communication with the PHP backend.
# No business logic. No Telegram code. Just HTTP.
import hmac
import hashlib
import time
import requests
from config import Config
from utils.retry import with_retry


class ApiService:
    """
    Communicates with the existing PHP MVC backend REST API.

    Authentication strategy:
        Every request carries two headers:
          X-Bot-Timestamp : Unix timestamp (seconds)
          X-Bot-Signature : HMAC-SHA256( SECRET + ":" + TIMESTAMP + ":" + BODY )

        The PHP backend verifies the signature and rejects requests older than 60 s.
        This prevents replay attacks without needing OAuth or session tokens.

    Example PHP verification (add to your existing API controller):
        $secret    = env('BOT_API_SECRET');
        $timestamp = $_SERVER['HTTP_X_BOT_TIMESTAMP'] ?? '';
        $signature = $_SERVER['HTTP_X_BOT_SIGNATURE'] ?? '';
        $body      = file_get_contents('php://input');
        $expected  = hash_hmac('sha256', $secret . ':' . $timestamp . ':' . $body, $secret);
        if (!hash_equals($expected, $signature) || abs(time() - (int)$timestamp) > 60) {
            http_response_code(401); exit;
        }
    """

    BASE = Config.PHP_API_BASE_URL
    SECRET = Config.PHP_API_SECRET

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    @with_retry()
    def create_product_request(
        self,
        telegram_id: int,
        description: str,
        image_bytes: bytes,
        filename: str,
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
        url = f"{self.BASE}/bot/requests"
        data = {
            "telegram_id": str(telegram_id),
            "description": description,
        }
        files = {"image": (filename, image_bytes, "image/jpeg")}
        body_for_sig = f"telegram_id={telegram_id}&description={description}"

        response = requests.post(
            url,
            data=data,
            files=files,
            headers=self._auth_headers(body_for_sig),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("success") and "request_id" in payload:
            return {"request_id": int(payload["request_id"])}
        print(f"[api] Unexpected response: {payload}")
        return None

    @with_retry()
    def get_request_status(self, request_id: int) -> dict | None:
        """
        GET /api/bot/requests/{id}

        Expected PHP response:
        {
            "request_id": 42,
            "status": "pending|approved|rejected",
            "price": "150.00",
            "admin_notes": "Good condition"
        }
        """
        url = f"{self.BASE}/bot/requests/{request_id}"
        response = requests.get(
            url,
            headers=self._auth_headers(""),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

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