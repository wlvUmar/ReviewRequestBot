# services/api_service.py — Handles ALL communication with the PHP backend.
# No business logic. No Telegram code. Just HTTP.
import hmac
import hashlib
import time
import requests
from config import Config
from utils.retry import with_retry
from utils.logger import log_msg

 
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

        data = {
            "telegram_id": str(telegram_id),
            "description": description,
        }
        body_for_sig = f"telegram_id={telegram_id}&description={description}"

        files = []
        for index, (image_bytes, filename) in enumerate(images):
            log_msg(f"[api] photo#{index + 1} filename={filename}, image_size={len(image_bytes)} bytes")
            files.append(("images[]", (filename, image_bytes, "image/jpeg")))

        headers = self._auth_headers(body_for_sig)
        log_msg(f"[api] Headers: X-Bot-Timestamp={headers.get('X-Bot-Timestamp')}, X-Bot-Signature={headers.get('X-Bot-Signature')[:16]}...") #type: ignore

        try:
            response = requests.post(
                url,
                data=data,
                files=files,
                headers=headers,
                timeout=20,
            )
            log_msg(f"[api] Response status: {response.status_code}")
            log_msg(f"[api] Response body: {response.text[:500]}")
            response.raise_for_status()

            payload = response.json()
            if payload.get("success") and "request_id" in payload:
                log_msg(f"[api] Success! Got request_id={payload['request_id']}")
                return {"request_id": int(payload["request_id"])}

            log_msg(f"[api] Unexpected response: {payload}")
            return None

        except requests.exceptions.ConnectionError as e:
            log_msg(f"[api] Connection error: {e}")
        except requests.exceptions.Timeout as e:
            log_msg(f"[api] Timeout error: {e}")
        except requests.exceptions.RequestException as e:
            log_msg(f"[api] Request error: {e}")

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
            "admin_notes": "Good condition",
            "contact_phone": "+998..."
        }
        """
        url = self._request_url_candidates(f"/bot/requests/{request_id}")
        log_msg(f"[api] Getting request status at {url}")

        try:
            response = requests.get(
                url,
                headers=self._auth_headers(""),
                timeout=10,
            )
            log_msg(f"[api] Status response: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log_msg(f"[api] Failed to get request status: {e}")

        return None

    @with_retry()
    def create_access_token(self, request_id: int, token: str) -> dict | None:
        """
        POST /api/bot/access-token
        Store an access token for a request (3-day expiration)
        
        Expected PHP response:
        {
            "success": true,
            "request_id": 42,
            "token": "abc123..."
        }
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
            response = requests.post(
                url,
                data=data,
                headers=headers,
                timeout=10,
            )
            log_msg(f"[api] Token response: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log_msg(f"[api] Failed to create access token: {e}")
        
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
