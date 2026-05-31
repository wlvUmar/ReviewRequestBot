import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import Config

_LOGGER_NAME = "reviewrequestbot"
_LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "reviewrequestbot.log"
_CONFIGURED = False


def _configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if Config.DEBUG else logging.INFO)
    logger.propagate = False

    if logger.handlers:
        _CONFIGURED = True
        return

    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    _configure_logging()
    if not name or name == _LOGGER_NAME:
        return logging.getLogger(_LOGGER_NAME)
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")