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

    print("Bot is running...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)

if __name__ == "__main__":
    main()