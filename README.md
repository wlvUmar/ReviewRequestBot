# Telegram Bot — PHP MVC CMS Integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram App                             │
│   User sends photo → Bot receives via TeleBot long-polling      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 1. /start, photo, description
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    bot.py (entry point)                         │
│   handlers/ ──► services/request_service.py                    │
│       │               │                                         │
│       │         db/repository.py    services/api_service.py    │
│       │               │                    │                    │
│       │      PHP-backed bot APIs      POST /api/bot/requests      │
│       │      /api/bot/users           /api/bot/mappings          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 2. Multipart image upload + metadata
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               Existing PHP MVC CMS Backend                      │
│   BotController@createRequest                                   │
│       │ stores in product_requests table (existing)             │
│       │ returns { "success": true, "request_id": 42 }          │
│                                                                  │
│   Admin reviews in existing admin panel                         │
│   AdminController calls BotController@sendReviewCallback        │
│       │ POST to bot callback server (signed HMAC)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 3. Signed webhook POST
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│         webhooks/callback_server.py (Flask, port 5055)          │
│   Verifies HMAC signature                                       │
│   Looks up telegram_id via /api/bot/mappings/{request_id}      │
│   Calls request_service.notify_review_result()                  │
│   Bot messages user with price / rejection reason               │
└─────────────────────────────────────────────────────────────────┘
```

## Sync Strategy

| Direction | Mechanism | Auth |
|-----------|-----------|------|
| Bot → PHP backend | REST API (multipart POST) | HMAC-SHA256 (`X-Bot-Timestamp`, `X-Bot-Signature`) |
| PHP backend → Bot | Webhook POST to Flask server | HMAC-SHA256 (`X-Callback-Timestamp`, `X-Callback-Signature`) |

Both directions use the same pattern: shared secret + timestamp + body → HMAC-SHA256. Requests older than 60 seconds are rejected to prevent replay attacks.

## Folder Structure

```
telegram_bot/
├── bot.py                        # Entry point only
├── config.py                     # Reads .env
├── requirements.txt
├── .env.example
├── handlers/
│   ├── __init__.py               # Registers all handlers
│   ├── start_handler.py          # /start command
│   ├── photo_handler.py          # Photo upload + /submit
│   └── text_handler.py           # Description text capture
├── services/
│   ├── request_service.py        # All business logic
│   └── api_service.py            # HTTP calls to PHP backend
├── db/
│   ├── connection.py             # MySQL connection pool
│   ├── repository.py             # All SQL queries
│   └── migrations/
│       └── 001_bot_tables.sql    # Bot-only tables (no CMS changes)
├── webhooks/
│   └── callback_server.py        # Flask: receives review results from PHP
├── utils/
│   ├── auth.py                   # HMAC helpers
│   ├── logger.py                 # Standard logging setup
│   └── retry.py                  # Retry decorator
├── logs/
│   └── reviewrequestbot.log      # Rotating app log file
└── php_integration/
    └── BotController.php         # Drop into your existing app/Controllers/Api/
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in secrets
cp .env.example .env
# Edit .env: BOT_TOKEN, PHP_API_BASE_URL, PHP_API_SECRET, CALLBACK_SECRET, DB_*

# 3. Run the DB migration (bot-only tables, safe to run on existing DB)
mysql -u root -p your_cms_db < db/migrations/001_bot_tables.sql

# 4. Add BotController.php to your PHP app
# Copy php_integration/BotController.php to app/Controllers/Api/
# Register routes:
#   POST /api/bot/requests
#   POST /api/bot/users
#   GET  /api/bot/users/{telegram_id}
#   POST /api/bot/users/{telegram_id}/phone
#   GET  /api/bot/users/{telegram_id}/phone
#   POST /api/bot/mappings
#   GET  /api/bot/mappings/{request_id}
#   POST /api/bot/mappings/{request_id}/claim
#   POST /api/bot/mappings/{request_id}/notified
#   POST /api/bot/mappings/{request_id}/release
# Call $botController->sendReviewCallback($request) from your AdminController

# 5. Add secrets to your PHP .env
# BOT_API_SECRET=same_value_as_PHP_API_SECRET_in_bot_.env
# BOT_CALLBACK_URL=http://bot-server:5055
# BOT_CALLBACK_SECRET=same_value_as_CALLBACK_SECRET_in_bot_.env

# 6. Start the bot
python bot.py
```

## API Payloads

### Bot → PHP: Create request
```
POST /api/bot/requests
Content-Type: multipart/form-data
X-Bot-Timestamp: 1718000000
X-Bot-Signature: <hmac>

Fields:
  telegram_id=123456789
  description=Nike Air Max, size 42, minor scuffs
  image=<binary JPEG>

Response 201:
{ "success": true, "request_id": 42 }
```

### PHP → Bot: Review result webhook
```
POST http://bot-server:5055/webhook/review-result
Content-Type: application/json
X-Callback-Timestamp: 1718000120
X-Callback-Signature: <hmac>

{
  "request_id": 42,
  "status":     "approved",
  "price":      "150.00",
  "notes":      "Good condition, fast reply."
}

Response 200:
{ "ok": true, "notified": true }
```

## DB Tables (bot-only, added to existing DB)

| Table | Purpose |
|-------|---------|
| `bot_users` | Stored through the PHP bot API; `telegram_id` is unique key |
| `bot_request_mappings` | Stored through the PHP bot API; maps `request_id` ↔ `telegram_id` and tracks notification status |

Your existing CMS tables are **never modified**.

## Scaling Notes

- Pending user flow data (photos/albums/caption/progress) is stored in Redis via TeleBot `StateRedisStorage` (`get_data`/`set_data`) for multi-process safety.
- Run the Flask callback server behind nginx for HTTPS (required for production).
- For high volume, move `with_retry` to a task queue (Celery + Redis).
- Future multi-admin: add `admin_id` to PHP `product_requests` table; no bot changes needed.