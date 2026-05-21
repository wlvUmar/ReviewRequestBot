import threading
import telebot
from config import Config
from handlers import register_handlers
from webhooks.callback_server import start_callback_server

def main():
    bot = telebot.TeleBot(Config.BOT_TOKEN, parse_mode="HTML")
    register_handlers(bot)

    # Start Flask callback server (receives webhooks FROM PHP backend) in background
    callback_thread = threading.Thread(
        target=start_callback_server,
        kwargs={"bot": bot},
        daemon=True
    )
    callback_thread.start()

    # Start background notification reconciler (polls PHP for status changes)
    try:
        from services.notification_service import NotificationService
        notifier = NotificationService(bot)
        notifier_thread = threading.Thread(target=notifier.run, daemon=True)
        notifier_thread.start()
    except Exception as e:
        print(f"[bot] Failed to start notification service: {e}")

    print("Bot is running...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)

if __name__ == "__main__":
    main()