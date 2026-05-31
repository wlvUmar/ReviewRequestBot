import asyncio
import traceback
from telebot.async_telebot import AsyncTeleBot
from telebot.storage import StateRedisStorage
from telebot import ExceptionHandler
from config import Config
from handlers import register_handlers
from webhooks.callback_server import start_callback_server
from utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    logger.info("[bot] Initializing async bot...")
    storage = StateRedisStorage(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
    )

    class LoggingExceptionHandler(ExceptionHandler):
        def handle(self, exception: Exception):
            logger.error("[bot] Handler exception:\n%s", traceback.format_exc())
            return True

    bot = AsyncTeleBot(
        Config.BOT_TOKEN,
        parse_mode="HTML",
        state_storage=storage,
        exception_handler=LoggingExceptionHandler(),  # type: ignore[arg-type]
    )  # type: ignore

    # Compatibility wrappers: ensure state/get/set methods are awaitable regardless of pyTelegramBotAPI version
    def _wrap_async(func):
        if asyncio.iscoroutinefunction(func):
            return func
        async def _wrapped(*args, **kwargs):
            res = func(*args, **kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        return _wrapped

    cs = getattr(bot, "current_states", None)
    if cs:
        if hasattr(cs, "get_data"):
            cs.get_data = _wrap_async(cs.get_data)
        if hasattr(cs, "reset_data"):
            cs.reset_data = _wrap_async(cs.reset_data)
        if hasattr(cs, "set_data"):
            cs.set_data = _wrap_async(cs.set_data)
        # wrap state-specific methods too (some versions expose set_state/get_state on storage)
        if hasattr(cs, "set_state"):
            cs.set_state = _wrap_async(cs.set_state)
        if hasattr(cs, "get_state"):
            cs.get_state = _wrap_async(cs.get_state)

    if hasattr(bot, "get_state"):
        bot.get_state = _wrap_async(bot.get_state)
    if hasattr(bot, "set_state"):
        bot.set_state = _wrap_async(bot.set_state)

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
