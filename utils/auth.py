import hmac
import hashlib
import time


def make_signature(secret: str, body: str, timestamp: str | None = None) -> tuple[str, str]:
    """
    Returns (timestamp, signature).
    signature = HMAC-SHA256( secret + ":" + timestamp + ":" + body )
    """
    ts = timestamp or str(int(time.time()))
    message = f"{secret}:{ts}:{body}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return ts, sig
 

def verify_signature(secret: str, body: str, timestamp: str, signature: str, max_age: int = 60) -> bool:
    """
    Verifies a signature and checks the timestamp is within max_age seconds.
    """
    if not all([secret, body is not None, timestamp, signature]):
        return False
    try:
        if abs(time.time() - int(timestamp)) > max_age:
            return False
    except ValueError:
        return False

    _, expected = make_signature(secret, body, timestamp)
    return hmac.compare_digest(expected, signature)