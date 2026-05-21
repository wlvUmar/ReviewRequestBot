# utils/retry.py — Decorator for retrying transient failures (network, DB, API timeouts).
import time
import functools
from config import Config


def with_retry(max_retries: int = None, delay: float = None):
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
                    print(f"[retry] {func.__name__} attempt {attempt}/{_max} failed: {e}")
                    if attempt < _max:
                        time.sleep(_delay * attempt)  # exponential-ish back-off
            print(f"[retry] {func.__name__} gave up after {_max} attempts.")
            return None
        return wrapper
    return decorator