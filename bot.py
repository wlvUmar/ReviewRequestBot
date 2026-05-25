import asyncio
from telebot.async_telebot import AsyncTeleBot
from config import Config
from handlers import register_handlers
from webhooks.callback_server import start_callback_server
from utils.logger import log_msg

async def main():
    log_msg("[bot] Initializing async bot...")
    bot = AsyncTeleBot(Config.BOT_TOKEN, parse_mode="HTML")
    
    log_msg("[bot] Registering handlers...")
    try:
        register_handlers(bot)
        log_msg("[bot] Handlers registered successfully")
    except Exception as e:
        log_msg(f"[bot] ERROR registering handlers: {e}")
        import traceback
        log_msg(traceback.format_exc())

    # Get the current event loop
    loop = asyncio.get_event_loop()

    log_msg(f"[bot] Starting Flask callback server on port {Config.CALLBACK_PORT}")
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
            log_msg("[bot] Notification service started")
        except Exception as e:
            log_msg(f"[bot] Failed to start notification service: {e}")
            import traceback
            log_msg(traceback.format_exc())
    else:
        log_msg("[bot] Notification polling disabled; using callback server only")

    log_msg("[bot] Bot is running...")
    log_msg("[bot] Starting polling (listening for messages)...")
    try:
        await bot.polling(timeout=30, long_polling_timeout=20)
    except Exception as e:
        log_msg(f"[bot] ERROR in polling loop: {e}")
        import traceback
        log_msg(traceback.format_exc())
    finally:
        if notifier_task:
            notifier_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())

