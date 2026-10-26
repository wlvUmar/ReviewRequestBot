import aiohttp
from config import Config
from product_processing.logger import get_logger

logger = get_logger(__name__)


async def search(query: str, session: aiohttp.ClientSession) -> list[dict]:
    """
    Use Perplexity via OpenRouter to get real search results with actual prices.
    """
    if not Config.SEARCH_API_KEY:
        return []

    payload = {
        "model": Config.SEARCH_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Search for current second-hand prices for: {query}\n"
                    f"Focus on OLX.uz, Avito.uz, Tashkent marketplace listings.\n"
                    f"Return only a list of actual listings with titles and prices in UZS. "
                    f"No explanation, just the listings."
                ), 
            }
        ],
        "max_tokens": 400,
    }

    headers = {
        "Authorization": f"Bearer {Config.SEARCH_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with session.post(
            Config.SEARCH_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"[search] OpenRouter returned {resp.status}: {text[:200]}")
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"[search] OpenRouter error for query={query!r}: {e}")
        return []

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not content:
        logger.warning(f"[search] Empty response for query={query!r}")
        return []

    logger.debug(f"[search] query={query!r} → {content[:200]}")

    # Return as a single result — llm.py's extract_item will parse it
    return [{
        "title": f"Market search: {query}",
        "link": "",
        "snippet": content,
    }]


async def multi_search(queries: list[str], session: aiohttp.ClientSession) -> list[dict]:
    import asyncio
    logger.debug(f"[search] Running {len(queries)} queries: {queries}")
    tasks = [search(q, session) for q in queries]
    results_nested = await asyncio.gather(*tasks)

    seen = set()
    merged = []
    for results in results_nested:
        for r in results:
            key = r["title"] + r["snippet"][:50]
            if key not in seen:
                seen.add(key)
                merged.append(r)

    logger.debug(f"[search] multi_search total unique results: {len(merged)}")
    return merged