from utils.logger import get_logger

logger = get_logger(__name__)

from .menu_handler import register_menu_handler
from .start_handler import register_start_handler
from .photo_handler import register_photo_handler
from .text_handler import register_text_handler

def register_handlers(bot):
    # Order matters: telebot uses the first handler that matches.
    # Commands/buttons first, free-text catch-alls last.
    logger.info("[handlers] registering menu_handler")
    register_menu_handler(bot)
    logger.info("[handlers] registering photo_handler")
    register_photo_handler(bot)
    logger.info("[handlers] registering start_handler")
    register_start_handler(bot)
    logger.info("[handlers] registering text_handler")
    register_text_handler(bot)
    logger.info("[handlers] all handlers registered")
