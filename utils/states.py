# utils.states
from telebot.asyncio_handler_backends import State, StatesGroup

class UserStates(StatesGroup):
    """User flow states"""
    start = State()
    awaiting_lang = State()
    awaiting_phone = State()
    awaiting_photo = State()
    awaiting_price = State()
    awaiting_description = State()
    submitting = State()
