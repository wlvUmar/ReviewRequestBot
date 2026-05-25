import threading
import telebot
from config import Config
from handlers import register_handlers
from webhooks.callback_server import start_callback_server
from utils.logger import log_msg

def main():
    log_msg("[bot] Initializing bot...")
    bot = telebot.TeleBot(Config.BOT_TOKEN, parse_mode="HTML")
    
    log_msg("[bot] Registering handlers...")
    try:
        register_handlers(bot)
        log_msg("[bot] Handlers registered successfully")
    except Exception as e:
        log_msg(f"[bot] ERROR registering handlers: {e}")
        import traceback
        log_msg(traceback.format_exc())

    log_msg(f"[bot] Starting Flask callback server on port {Config.CALLBACK_PORT}")
    callback_thread = threading.Thread(
        target=start_callback_server,
        kwargs={"bot": bot},
        daemon=True
    )
    callback_thread.start()
 
    # Start background notification reconciler (polls PHP for status changes)
    if Config.ENABLE_NOTIFY_POLLING:
        try:
            from services.notification_service import NotificationService
            notifier = NotificationService(bot)
            notifier_thread = threading.Thread(target=notifier.run, daemon=True)
            notifier_thread.start()
            log_msg("[bot] Notification service started")
        except Exception as e:
            log_msg(f"[bot] Failed to start notification service: {e}")
            import traceback
            log_msg(traceback.format_exc())
    else:
        log_msg("[bot] Notification polling disabled; using callback server only")

    log_msg("[bot] Bot is running...")
    log_msg("[bot] Starting infinity_polling (listening for messages)...")
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=20)
    except Exception as e:
        log_msg(f"[bot] ERROR in polling loop: {e}")
        import traceback
        log_msg(traceback.format_exc())

if __name__ == "__main__":
    main()
