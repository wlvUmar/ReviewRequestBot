"""
utils/currency.py — Normalize user-entered prices to UZS.

Users enter prices in all sorts of ways:
  "150000", "150 000", "150к", "150k", "150usd", "150$", "150 у.е.", "12"

Rules:
  - Contains "usd", "$", "у.е.", "уе", "dollar" → treat as USD → multiply by USD_RATE
  - Pure number < USD_THRESHOLD → treat as USD → multiply by USD_RATE
  - Everything else → treat as UZS

USD_THRESHOLD = 10000: if user types a bare number below this it's almost
certainly USD (no one prices a fridge at "500 UZS").
"""

import re

USD_RATE = 12700        # 1 USD ≈ 12,700 UZS  (update periodically or pull live)
USD_THRESHOLD = 10_000  # bare numbers below this are treated as USD


# Tokens that signal the user means USD 
_USD_SIGNALS = re.compile(
    r"usd|\$|у\.е\.?|уе(?!\w)|dollar|доллар",
    re.IGNORECASE,
)

# Strip everything that isn't a digit, dot, or comma
_DIGIT_ONLY = re.compile(r"[^\d.,]")

# Collapse thousands separators written as spaces or apostrophes
_SPACE_SEP = re.compile(r"(\d)[\s'](\d)")


def parse_price_to_uzs(raw: str) -> tuple[int, str]:
    """
    Parse a raw user price string into (uzs_amount, display_string).

    Returns:
        uzs_amount   — integer UZS value
        display      — human-readable string shown in admin panel, e.g.
                       "800,000 UZS"  or  "800,000 UZS ($63)"

    Raises ValueError if no valid number can be extracted.
    """
    text = raw.strip()

    # Detect currency intent before stripping letters
    is_usd = bool(_USD_SIGNALS.search(text))

    # Normalise "к" / "k" suffix (кило = thousand)
    kilo_match = re.search(r"([\d.,]+)\s*[кk](?!\w)", text, re.IGNORECASE)
    if kilo_match:
        num_str = kilo_match.group(1).replace(",", ".")
        try:
            value = float(num_str) * 1000
        except ValueError:
            raise ValueError(f"Cannot parse number from: {raw!r}")
        # Explicit кило suffix always means UZS in local context — never auto-upgrade to USD
        # (nobody says "1.5к usd"; they say "150 usd")
    else:
        # Remove thousands-space separators like "150 000"
        text_clean = _SPACE_SEP.sub(r"\1\2", text)
        text_clean = _DIGIT_ONLY.sub("", text_clean)
        # Collapse stray multiple dots left over from abbreviations like "у.е."
        text_clean = re.sub(r"\.{2,}", "", text_clean)
        # If there's a dot AND a comma, the last one is decimal separator
        if "." in text_clean and "," in text_clean:
            # e.g. "1.200,50" → European format
            text_clean = text_clean.replace(".", "").replace(",", ".")
        elif "," in text_clean:
            # Could be thousands separator ("1,200,000") or decimal ("1,5")
            parts = text_clean.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Decimal comma: "1,5" → 1.5
                text_clean = text_clean.replace(",", ".")
            else:
                # Thousands commas: "1,200,000" → "1200000"
                text_clean = text_clean.replace(",", "")

        if not text_clean:
            raise ValueError(f"No digits found in: {raw!r}")

        try:
            value = float(text_clean)
        except ValueError:
            raise ValueError(f"Cannot parse number from: {raw!r}")

    if value <= 0:
        raise ValueError(f"Price must be positive, got: {value}")

    # Auto-detect USD if no explicit signal but value is suspiciously small
    if not is_usd and value < USD_THRESHOLD:
        is_usd = True

    if is_usd:
        uzs = int(round(value * USD_RATE))
        usd_val = value
        display = f"{uzs:,} UZS (${usd_val:,.0f})".replace(",", " ")
    else:
        uzs = int(round(value))
        usd_equiv = uzs / USD_RATE
        display = f"{uzs:,} UZS (≈${usd_equiv:,.0f})".replace(",", " ")

    return uzs, display


def uzs_to_usd(uzs: int) -> float:
    return round(uzs / USD_RATE, 2)


def format_uzs(uzs: int) -> str:
    """'1 200 000 UZS'"""
    return f"{uzs:,} UZS".replace(",", " ")