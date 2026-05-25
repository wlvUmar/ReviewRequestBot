from pathlib import Path
from datetime import datetime

LOG_FILE = Path(__file__).resolve().parents[1] / "reviewrequestbot.log"

def log_msg(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} {msg}\n")
            f.flush()
    except Exception:
        pass
 