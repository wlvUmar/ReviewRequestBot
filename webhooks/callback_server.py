import asyncio
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from config import Config
from db.repository import BotRepository
from services.request_service import RequestService
from utils.logger import get_logger

logger = get_logger(__name__)


def start_callback_server(bot, loop):
    """Start Flask server in background. Receives callbacks from PHP."""
    app = Flask(__name__)
    logger.info("[callback] server starting on %s:%s", Config.CALLBACK_HOST, Config.CALLBACK_PORT)

    @app.route("/webhook/review-result", methods=["POST"])
    def review_result():
        # --- Verify HMAC signature from PHP ---
        timestamp = request.headers.get("X-Callback-Timestamp", "")
        signature = request.headers.get("X-Callback-Signature", "")
        raw_body = request.get_data(as_text=True)

        if not _verify_signature(raw_body, timestamp, signature):
            logger.warning("[callback] unauthorized request")
            return jsonify({"error": "unauthorized"}), 401

        if abs(time.time() - int(timestamp)) > 60:
            logger.warning("[callback] request expired")
            return jsonify({"error": "request expired"}), 401

        data = request.get_json(silent=True)
        if not data or "request_id" not in data or "status" not in data:
            logger.warning("[callback] invalid payload body=%s", raw_body[:500])
            return jsonify({"error": "invalid payload"}), 400

        request_id = int(data["request_id"])
        status = data.get("status", "")
        price = data.get("price", "")
        notes = data.get("notes", "")
        contact_phone = data.get("contact_phone", "")
        logger.info(
            "[callback] payload request_id=%s status=%s price=%s contact_phone=%s",
            request_id,
            status,
            price,
            contact_phone or "EMPTY",
        )

        # Fire and forget — don't wait for Telegram
        repo = BotRepository()
        svc = RequestService(bot, repo)
        asyncio.run_coroutine_threadsafe(
            svc.notify_review_result(request_id, status, price, notes, contact_phone),
            loop
        )

        logger.info("[callback] Accepted request_id=%s, notifying in background", request_id)
        return jsonify({"ok": True, "accepted": True}), 202

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    app.run(host=Config.CALLBACK_HOST, port=Config.CALLBACK_PORT, threaded=True)


def _verify_signature(body: str, timestamp: str, signature: str) -> bool:
    secret = Config.CALLBACK_SECRET
    if not secret or not timestamp or not signature:
        return False
    expected = hmac.new(
        secret.encode(),
        (body + timestamp).encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)