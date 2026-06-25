# Simplified utils/currency.py - just extract number, no conversion

import re

USD_RATE = 12000

def parse_price(raw: str) -> str:
    """
    Validate that user input contains a recognizable number, and return the
    input string unchanged (currency symbols/units intact) so a downstream
    LLM can do the actual parsing (multipliers, currency conversion, etc).

    Examples:
        "700 тыс"   -> "700 тыс"
        "150 usd"   -> "150 usd"
        "1,500,000" -> "1,500,000"
        "700 k"     -> "700 k"
        "49$"       -> "49$"
        "1.5 млн"   -> "1.5 млн"
        "€700"      -> "€700"
    """
    text = raw.strip()

    if not text or not re.search(r"\d", text):
        raise ValueError(f"No number found in: {raw!r}")

    return text

def format_uzs(uzs: int) -> str:
    """Format integer UZS for display: '1 200 000 UZS'"""
    return f"{uzs:,} UZS".replace(",", " ") 