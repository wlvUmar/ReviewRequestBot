# webhooks/callback_server.py — Flask server that listens for callbacks FROM the PHP backend.
#
# Sync architecture:
#   When an admin reviews a request in the PHP admin panel, the PHP backend
#   sends a signed POST to this server. The bot then messages the user.
#
# PHP should POST to: http://bot-server:5055/webhook/review-result
#
# Example PHP code to call this (add to your existing AdminController):
#   $payload = json_encode([
#       'request_id' => $request->id,
#       'status'     => 'approved',       // or 'rejected'
#       'price'      => '150.00',
#       'notes'      => 'Good condition',
#   ]);
#   $timestamp = time();
#   $signature = hash_hmac('sha256', $payload . $timestamp, env('BOT_CALLBACK_SECRET'));
#   Http::withHeaders([
#       'X-Callback-Timestamp' => $timestamp,
#       'X-Callback-Signature' => $signature,
#       'Content-Type'         => 'application/json',
#   ])->post(env('BOT_CALLBACK_URL') . '/webhook/review-result', json_decode($payload, true));

from flask import Flask, request, jsonify
import hmac
import hashlib
import time
import telebot
from config import Config
from db.repository import BotRepository
from services.request_service import RequestService


def start_callback_server(bot: telebot.TeleBot):
    app = Flask(__name__)

    @app.route("/webhook/review-result", methods=["POST"])
    def review_result():
        # --- Verify HMAC signature from PHP ---
        timestamp = request.headers.get("X-Callback-Timestamp", "")
        signature = request.headers.get("X-Callback-Signature", "")
        raw_body = request.get_data(as_text=True)

        if not _verify_signature(raw_body, timestamp, signature):
            return jsonify({"error": "unauthorized"}), 401

        if abs(time.time() - int(timestamp)) > 60:
            return jsonify({"error": "request expired"}), 401

        # --- Parse payload ---
        # Expected payload:
        # {
        #     "request_id": 42,
        #     "status":     "approved",   // or "rejected"
        #     "price":      "150.00",     // empty string if rejected
        #     "notes":      "Great item"
        # }
        data = request.get_json(silent=True)
        if not data or "request_id" not in data or "status" not in data:
            return jsonify({"error": "invalid payload"}), 400

        request_id = int(data["request_id"])
        status = data.get("status", "")
        price = data.get("price", "")
        notes = data.get("notes", "")

        # --- Notify user via bot ---
        repo = BotRepository()
        svc = RequestService(bot, repo)
        sent = svc.notify_review_result(request_id, status, price, notes)

        if sent:
            return jsonify({"ok": True, "notified": True}), 200
        else:
            # PHP should retry — request_id not found yet (race) or user blocked bot
            return jsonify({"ok": False, "notified": False}), 404

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    app.run(host=Config.CALLBACK_HOST, port=Config.CALLBACK_PORT)


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