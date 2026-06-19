from utils.logger import get_logger

logger = get_logger(__name__)

from .start_handler import register_start_handler
from .photo_handler import register_photo_handler
from .text_handler import register_text_handler

def register_handlers(bot):
    logger.info("[handlers] registering photo_handler")
    register_photo_handler(bot)
    logger.info("[handlers] registering start_handler")
    register_start_handler(bot)
    logger.info("[handlers] registering text_handler")
    register_text_handler(bot)
    logger.info("[handlers] all handlers registered")