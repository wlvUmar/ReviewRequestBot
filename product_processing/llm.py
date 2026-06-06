"""
product_processing/llm.py

Two-stage LLM pipeline:
  1. Cheap model  → generate search queries
  2. Main model   → extract structured item data from description + search results

Currency note: ALL prices the LLM returns are in UZS.
Profit math is done in Python (request_service.py), never by the LLM.
"""

import json
import aiohttp
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal call helper
# ---------------------------------------------------------------------------

async def _call(
    model: str,
    system: str,
    user: str,
    session: aiohttp.ClientSession,
    max_tokens: int = 600,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    logger.debug(f"[llm] calling model={model} max_tokens={max_tokens}")
    try:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT),
        ) as resp:
            data = await resp.json()
    except Exception as e:
        logger.error(f"[llm] call failed model={model}: {e}")
        raise RuntimeError(f"LLM call failed: {e}")

    raw = data["choices"][0]["message"]["content"].strip()
    logger.debug(f"[llm] raw response ({len(raw)} chars): {raw[:200]}")
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ---------------------------------------------------------------------------
# Step 1 — cheap model: generate search queries
# ---------------------------------------------------------------------------

_QUERY_SYSTEM = """You generate short web search queries to find the current \
market price of a second-hand item in Tashkent, Uzbekistan.

Return ONLY a JSON array of 2-3 strings. Each query should be specific enough \
to find real listings.
Target sites: OLX.uz, Avito.uz, Birbir.uz.

Example output:
["Samsung холодильник 350L цена Ташкент", "холодильник Samsung бу купить Узбекистан olx"]

No markdown, no explanation, just the JSON array."""


async def get_search_queries(text: str, session: aiohttp.ClientSession) -> list[str]:
    logger.debug(f"[llm] generating search queries for: {text[:100]}")
    raw = await _call(Config.QUERY_MODEL, _QUERY_SYSTEM, text, session, max_tokens=150)
    result = _parse_json(raw, "query model")
    if not isinstance(result, list):
        logger.warning(f"[llm] query model returned non-list: {result}")
        return [text]
    return [str(q) for q in result if q][:3]


# ---------------------------------------------------------------------------
# Step 2 — main model: extract structured item data
# ---------------------------------------------------------------------------

# Items we buy — used to guide the LLM's is_in_category decision.
# Keep this in sync with what your business actually buys.
_CATEGORY_DESCRIPTION = """
We buy second-hand household appliances and furniture in Tashkent. Specifically:
- Refrigerators and freezers
- Washing machines and dryers
- Air conditioners (split systems, window units)
- Gas stoves and electric cookers
- TVs and large monitors (32"+ screens)
- Dishwashers
- Microwave ovens
- Water heaters (boilers)
- Vacuum cleaners
- Furniture (sofas, beds, wardrobes, tables, chairs, shelving)
- Carpets and large rugs
- Large kitchen appliances in general

We do NOT buy:
- Smartphones, tablets, laptops, computers
- Small electronics (headphones, joysticks, game controllers, phone cases,
  chargers, cables, smartwatches, cameras)
- Clothing, shoes, accessories
- Tools, spare parts, components
- Baby items (strollers, car seats)
- Exercise equipment
- Bicycles, scooters
- Books, toys, games
"""

_EXTRACT_SYSTEM = f"""You are analyzing a second-hand item listing from Tashkent, Uzbekistan.
You receive the original request text AND web search results showing current market prices.

{_CATEGORY_DESCRIPTION}

Return ONLY a valid JSON object with these exact fields:

{{
  "product_name": "clean descriptive name in Russian",
  "brand": "brand name or null",
  "model": "model identifier or null",
  "condition": one of ["new", "like_new", "good", "fair", "damaged", "unknown"],
  "is_in_category": true or false,
  "market_price_uzs": integer UZS or null,
  "price_confidence": one of ["high", "medium", "low", "none"],
  "price_notes": "one short sentence on how price was determined, or null",
  "needs_repair": true or false,
  "repair_type": "short description of repair needed, or null",
  "repair_cost_uzs": integer UZS or null
}}

Rules:
- is_in_category: true only if the item clearly matches what we buy (see list above).
  If unsure, set true — we would rather review borderline cases than miss them.
- market_price_uzs: median resale price for this item in working condition in
  Tashkent. Base it on search results. null if no data.
- repair_cost_uzs: realistic Tashkent repair shop estimate. null if no repair needed.
- All prices MUST be in UZS (Uzbek sum). If search results show USD, convert
  using 1 USD = 12700 UZS.
- price_confidence: high = 3+ consistent listings, medium = 1-2 listings,
  low = extrapolating, none = no data found.
- No markdown, no comments — raw JSON only.
"""


async def extract_item(
    text: str,
    search_results: list[dict],
    session: aiohttp.ClientSession,
) -> dict:
    logger.debug(
        f"[llm] extracting item text={text[:100]!r} search_results={len(search_results)}"
    )
    search_block = "\n\n".join(
        f"[{i + 1}] {r['title']}\n{r['snippet']}"
        for i, r in enumerate(search_results)
        if r.get("title") or r.get("snippet")
    ) or "No search results found."

    user_msg = f"Item request:\n{text}\n\nSearch results:\n{search_block}"
    raw = await _call(Config.MAIN_MODEL, _EXTRACT_SYSTEM, user_msg, session, max_tokens=600)
    result = _parse_json(raw, "extract model")
    logger.debug(f"[llm] extracted: {result}")
    return result  # type: ignore


# ---------------------------------------------------------------------------
# Repair query generation (unchanged logic, kept for completeness)
# ---------------------------------------------------------------------------

_REPAIR_QUERY_SYSTEM = """You generate short web search queries to find the \
repair cost of a specific broken item in Tashkent, Uzbekistan.

Return ONLY a JSON array of 2 strings. Be specific about the repair type and device.
Target: local repair shops in Tashkent.

Example output for "стиральная машина замена подшипника":
["замена подшипника стиральная машина цена Ташкент", "ремонт стиральной машины подшипник сколько стоит"]

No markdown, no explanation, just the JSON array."""


async def get_repair_search_queries(
    repair_type: str,
    product_name: str,
    session: aiohttp.ClientSession,
) -> list[str]:
    text = f"Repair needed: {repair_type} for {product_name}"
    logger.debug(f"[llm] generating repair search queries for: {text}")
    raw = await _call(Config.QUERY_MODEL, _REPAIR_QUERY_SYSTEM, text, session, max_tokens=100)
    result = _parse_json(raw, "repair query model")
    if not isinstance(result, list):
        logger.warning(f"[llm] repair query model returned non-list: {result}")
        return [f"{repair_type} ремонт цена Ташкент"]
    queries = [str(q) for q in result if q][:2]
    logger.debug(f"[llm] generated repair queries: {queries}")
    return queries


# ---------------------------------------------------------------------------
# Shared JSON parser
# ---------------------------------------------------------------------------

def _parse_json(raw: str, context: str) -> dict | list:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[llm] invalid JSON from {context}: {e} | raw={raw[:300]}")
        raise RuntimeError(f"Invalid JSON from {context}: {e}\nRaw: {raw}") 