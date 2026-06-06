import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # PHP Backend
    PHP_API_BASE_URL: str = os.getenv("PHP_API_BASE_URL", "https://yoursite.com/api")
    PHP_API_SECRET: str = os.getenv("PHP_API_SECRET", "")   # Shared HMAC secret

    # Callback server (Flask — receives webhooks FROM PHP)
    CALLBACK_HOST: str = os.getenv("CALLBACK_HOST", "0.0.0.0")
    CALLBACK_PORT: int = int(os.getenv("CALLBACK_PORT", "5055"))
    CALLBACK_SECRET: str = os.getenv("CALLBACK_SECRET", "") # PHP signs callbacks with this

    # Redis (for storing lightweight user state like language)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # MySQL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "your_cms_db")
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Behaviour
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "2.0"))
    IMAGE_MAX_MB: int = int(os.getenv("IMAGE_MAX_MB", "10"))
    MAX_PHOTOS_PER_REQUEST: int = int(os.getenv("MAX_PHOTOS_PER_REQUEST", "4"))
    # Poll interval (seconds) for background notification reconciler
    NOTIFY_POLL_INTERVAL: int = int(os.getenv("NOTIFY_POLL_INTERVAL", "60"))
    ENABLE_NOTIFY_POLLING: bool = os.getenv("ENABLE_NOTIFY_POLLING", "0") == "1"
    
    # Admin notifications
    ADMIN_IDS: list[int] = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    
    # Logging (DEBUG=1 for verbose, DEBUG=0 for errors only)
    # --- LLM (main extraction model) ---
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your_key_here")
    MAIN_MODEL = os.getenv("MAIN_MODEL", "openai/gpt-4o-mini")

    # --- LLM (cheap model just for generating search queries) ---
    QUERY_MODEL = os.getenv("QUERY_MODEL", "openai/gpt-4o-mini")

    # --- SearXNG ---
    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")

    # Fast-sell ratio: what fraction of market price you can realistically get quickly
    FAST_SELL_RATIO = float(os.getenv("FAST_SELL_RATIO", "0.82"))

    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
    PRICER_URL: str = os.getenv("PRICER_URL", "http://localhost:8001")
    DEBUG: bool = os.getenv("DEBUG", "1") == "1"
     