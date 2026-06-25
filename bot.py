import asyncio
import signal
import traceback
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_storage import StateRedisStorage
from telebot import ExceptionHandler, asyncio_filters
from config import Config
from handlers import register_handlers
from webhooks.callback_server import start_callback_server
from utils.logger import get_logger
from telebot.states.asyncio.middleware import StateMiddleware

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
            return False

    bot = AsyncTeleBot(
        Config.BOT_TOKEN,
        parse_mode="HTML",
        state_storage=storage,
        exception_handler=LoggingExceptionHandler(),  # type: ignore[arg-type]
    )  # type: ignore

    logger.info("[bot] Registering handlers...")
    try:
        register_handlers(bot)
        logger.info("[bot] Handlers registered successfully")
    except Exception:
        logger.exception("[bot] ERROR registering handlers")
    for i, handler in enumerate(bot.message_handlers):
        logger.debug(i)
        logger.debug(handler["function"].__name__)
        logger.debug(handler["filters"])

    bot.setup_middleware(StateMiddleware(bot))
    bot.add_custom_filter(asyncio_filters.StateFilter(bot))
    loop = asyncio.get_event_loop()

    logger.info("[bot] Starting Flask callback server on port %s", Config.CALLBACK_PORT)
    import threading
    callback_thread = threading.Thread(
        target=start_callback_server,
        kwargs={"bot": bot, "loop": loop},
        daemon=True
    )
    callback_thread.start()

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

    # --- graceful shutdown wiring ---
    polling_task = asyncio.create_task(bot.infinity_polling(timeout=30))
    stop_event = asyncio.Event()

    def _handle_shutdown_signal(sig_name):
        logger.warning("[bot] Received %s, shutting down...", sig_name)
        stop_event.set()
        polling_task.cancel()
        if notifier_task:
            notifier_task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler = getattr(loop, "add_signal_handler", None)
        loop.add_signal_handler(sig, _handle_shutdown_signal, sig.name)
    # --- end shutdown wiring ---

    logger.info("[bot] Bot is running...")
    logger.info("[bot] Starting polling (listening for messages)...")
    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info("[bot] Polling task cancelled, closing bot session...")
    except Exception:
        logger.exception("[bot] ERROR in polling loop")
    finally:
        try:
            await bot.close_session()
            logger.info("[bot] Bot session closed cleanly")
        except Exception:
            logger.exception("[bot] Error closing bot session")
        if notifier_task and not notifier_task.done():
            notifier_task.cancel()
            try:
                await notifier_task
            except asyncio.CancelledError:
                pass
        logger.info("[bot] Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass