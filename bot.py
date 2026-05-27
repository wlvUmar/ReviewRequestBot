import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot.storage import StateRedisStorage
from config import Config
from handlers import register_handlers
from webhooks.callback_server import start_callback_server
from utils.logger import get_logger

logger = get_logger(__name__)

async def main():
    logger.info("[bot] Initializing async bot...")
    storage = StateRedisStorage(host='localhost', port=6379, db=0)
    bot = AsyncTeleBot(Config.BOT_TOKEN, parse_mode="HTML", state_storage=storage) #type: ignore
    
    logger.info("[bot] Registering handlers...")
    try:
        register_handlers(bot)
        logger.info("[bot] Handlers registered successfully")
    except Exception:
        logger.exception("[bot] ERROR registering handlers")

    # Get the current event loop
    loop = asyncio.get_event_loop()

    logger.info("[bot] Starting Flask callback server on port %s", Config.CALLBACK_PORT)
    import threading
    callback_thread = threading.Thread(
        target=start_callback_server,
        kwargs={"bot": bot, "loop": loop},
        daemon=True
    )
    callback_thread.start()
 
    # Start background notification reconciler (polls PHP for status changes)
    notifier_task = None
    if Config.ENABLE_NOTIFY_POLLING:
        try:
            from services.notification_service import NotificationService
            notifier = NotificationService(bot)
            notifier_task = asyncio.create_task(notifier.run())
            logger.info("[bot] Notification service started")
        except Exception:
            logger.exception("[bot] Failed to start notification service")
    else:
        logger.info("[bot] Notification polling disabled; using callback server only")

    logger.info("[bot] Bot is running...")
    logger.info("[bot] Starting polling (listening for messages)...")
    try:
        await bot.polling(timeout=30)
    except Exception:
        logger.exception("[bot] ERROR in polling loop")
    finally:
        if notifier_task:
            notifier_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
