# utils/retry.py — Decorator for retrying transient failures (network, DB, API timeouts).
import asyncio
import time
import functools
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


def with_retry(max_retries: int | None = None, delay: float | None = None):
    """
    Decorator factory. Retries the decorated function on exception.

    Usage:
        @with_retry()
        def call_php_api(...): ...

        @with_retry(max_retries=5, delay=1.0)
        def critical_call(...): ...
    """
    _max = max_retries if max_retries is not None else Config.MAX_RETRIES
    _delay = delay if delay is not None else Config.RETRY_DELAY

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, _max + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "[retry] %s attempt %s/%s failed: %s",
                        func.__name__,
                        attempt,
                        _max,
                        e,
                    )
                    if attempt < _max:
                        time.sleep(_delay * attempt)  # exponential-ish back-off
            logger.error("[retry] %s gave up after %s attempts.", func.__name__, _max)
            return None
        return wrapper
    return decorator


def async_with_retry(max_retries: int | None = None, delay: float | None = None):
    """
    Async decorator factory. Retries the decorated async function on exception.

    Usage:
        @async_with_retry()
        async def call_php_api_async(...): ...

        @async_with_retry(max_retries=5, delay=1.0)
        async def critical_call(...): ...
    """
    _max = max_retries if max_retries is not None else Config.MAX_RETRIES
    _delay = delay if delay is not None else Config.RETRY_DELAY

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, _max + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "[retry] %s attempt %s/%s failed: %s",
                        func.__name__,
                        attempt,
                        _max,
                        e,
                    )
                    if attempt < _max:
                        await asyncio.sleep(_delay * attempt)  # exponential-ish back-off
            logger.error("[retry] %s gave up after %s attempts.", func.__name__, _max)
            return None
        return wrapper
    return decorator