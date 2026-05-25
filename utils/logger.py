from pathlib import Path
from datetime import datetime
from config import Config

LOG_FILE = Path(__file__).resolve().parents[1] / "reviewrequestbot.log"

def log_msg(msg: str, level: str = "INFO") -> None:
    """
    Log a message to file.
    
    Args:
        msg: Message to log
        level: Log level - "INFO", "ERROR", "DEBUG", "WARNING"
               If DEBUG mode is off, only ERROR and WARNING are logged
    
    Usage:
        log_msg("Something happened")  # INFO level
        log_msg("API error", level="ERROR")  # ERROR level
        log_msg("Detailed info", level="DEBUG")  # Only if DEBUG=1
    """
    # Skip debug logs if DEBUG mode is off
    if not Config.DEBUG and level == "DEBUG":
        return
    
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} [{level}] {msg}\n")
            f.flush()
    except Exception:
        pass
 