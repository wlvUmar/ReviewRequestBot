# Simplified utils/currency.py - just extract number, no conversion

import re

USD_RATE = 12000

def parse_price(raw: str) -> str:
    """
    Extract the numeric part from user input.
    Return it as-is, no currency conversion.
    
    Examples:
        "700 тыс" → "700"
        "150 usd" → "150"
        "1,500,000" → "1500000"
        "700 k" → "700"
    """
    text = raw.strip()
    
    # Remove spaces and apostrophes that separate thousands
    text = re.sub(r"[\s']", "", text)
    
    # Extract all digit sequences and dots/commas
    # Then clean up to just digits (remove commas, keep dots if decimal)
    match = re.search(r"[\d.,]+", text)
    
    if not match:
        raise ValueError(f"No number found in: {raw!r}")
    
    number = match.group(0)
    
    # Normalize: remove commas (thousands separators), collapse multiple dots
    number = number.replace(",", "")
    number = re.sub(r"\.{2,}", "", number)
    
    # Remove trailing dots (from abbreviations like "тыс.")
    number = number.rstrip(".")
    
    # Must have at least one digit
    if not number or not any(c.isdigit() for c in number):
        raise ValueError(f"No valid number in: {raw!r}")
    
    return number


def format_uzs(uzs: int) -> str:
    """Format integer UZS for display: '1 200 000 UZS'"""
    return f"{uzs:,} UZS".replace(",", " ") 