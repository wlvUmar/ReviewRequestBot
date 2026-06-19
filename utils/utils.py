# handlers/utils.py
import re
from utils.logger import get_logger

logger = get_logger(__name__)


def validate_and_normalize_phone(raw_phone: str) -> tuple[str | None, str]:

    if not raw_phone or not isinstance(raw_phone, str):
        return None, "Empty phone number"

    # Remove whitespace
    phone = raw_phone.strip()

    # Remove common separators: spaces, dashes, parentheses
    phone = re.sub(r'[\s\-\(\)]', '', phone)

    logger.debug(f"[start_handler._validate_and_normalize_phone] Normalizing phone: {raw_phone} -> {phone}")

    # Already has +
    if phone.startswith("+"):
        if len(phone) < 10:
            return None, "Phone number too short"
        logger.debug(f"[start_handler._validate_and_normalize_phone] Phone already has +: {phone}")
        return phone, ""

    # Handle Uzbekistan numbers: 998XXXXXXXXX or 0XXXXXXXXX or 9XXXXXXXXX
    # Standard Uzbek mobile: +998 9X XXX XX XX (9 digits after country code)

    # Remove leading 0 if present (0998... -> 998...)
    if phone.startswith("0"):
        phone = phone[1:]
        logger.debug(f"[start_handler._validate_and_normalize_phone] Removed leading 0: {phone}")

    # Add country code if missing
    if phone.startswith("998"):
        phone = "+" + phone
    elif phone.startswith("9") and len(phone) == 9:
        # Just the 9-digit part, add country code
        phone = "+998" + phone
    elif len(phone) == 9:
        # Assume it's the 9-digit part
        phone = "+998" + phone
    else:
        # Try to detect if it's a full number without country code
        # Check if it matches Uzbek pattern (starts with 9, has 9 digits)
        if re.match(r'^9\d{8}$', phone):
            phone = "+998" + phone
        else:
            return None, "Invalid phone number format"

    if not re.match(r'^\+998[0-9]{9}$', phone):
        return None, "Invalid phone number format"

    logger.debug(f"[start_handler._validate_and_normalize_phone] Valid normalized phone: {phone}")
    return phone, ""