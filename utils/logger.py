import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import Config

_LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "reviewrequestbot.log"
_CONFIGURED = False


def _configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(Config.LOG_LEVEL)
    root.handlers.clear()

    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for noisy in ("urllib3", "asyncio", "telebot", "werkzeug", "aiohttp", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    _configure_logging()
    return logging.getLogger(name or "reviewrequestbot")