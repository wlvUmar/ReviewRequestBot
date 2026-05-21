from .start_handler import register_start_handler
from .photo_handler import register_photo_handler
from .text_handler import register_text_handler

def register_handlers(bot):
    register_start_handler(bot)
    register_photo_handler(bot)
    register_text_handler(bot)