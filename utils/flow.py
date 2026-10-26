# utils/flow.py — small helpers shared by the conversation handlers.
from config import Config

# Everything the user has entered for the request currently being built.
FLOW_KEYS = ("photos", "caption", "albums", "description", "preview", "desired_price", "sending")

# States in which a request is being built (used by /cancel, wrong-state hints).
IN_FLOW_STATES = ("awaiting_photo", "awaiting_description", "awaiting_price", "submitting")


def clear_flow_data(data: dict) -> dict:
    """Drop the half-built request from the user's state data (keeps lang, phone, last_request_id)."""
    for key in FLOW_KEYS:
        data.pop(key, None)
    return data


def state_is(current: str | None, name: str) -> bool:
    """True if the stored state name (e.g. 'UserStates:awaiting_price') ends with `name`."""
    return bool(current) and str(current).endswith(name)


def in_flow(current: str | None) -> bool:
    return any(state_is(current, s) for s in IN_FLOW_STATES)


def is_ignored_admin(telegram_id: int) -> bool:
    """Admins don't use the customer flow unless DEBUG is on (so they can test)."""
    return telegram_id in Config.ADMIN_IDS and not Config.DEBUG
