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

# Single source of truth — passed into prompts dynamically so there's no drift
_USD_RATE = Config.FAST_SELL_RATIO  # reuse from config? No — use currency.py's rate
# Import the rate directly from currency.py so it's never duplicated
from utils.currency import USD_RATE as _USD_RATE


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

_QUERY_SYSTEM = """Ты генерируешь поисковые запросы на русском языке для поиска \
актуальных цен на б/у товары в Ташкенте, Узбекистан.

Верни ТОЛЬКО JSON-массив из 2-3 строк. Каждый запрос должен:
- быть на русском языке (именно так ищут в Ташкенте)
- содержать название товара, бренд/модель если известны
- содержать слово "Ташкент" или "Узбекистан" или "olx.uz"
- быть конкретным — чтобы найти реальные объявления с ценами

Пример для "Samsung холодильник двухкамерный 350L немного царапин":
["Samsung холодильник б/у цена Ташкент", "холодильник Samsung 350L купить Узбекистан olx", "Samsung холодильник двухкамерный бу Ташкент цена"]

Никакого markdown, никаких пояснений — только JSON-массив."""


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

_CATEGORY_DESCRIPTION = """
Мы покупаем следующие б/у товары в Ташкенте:
- Холодильники и морозильники
- Стиральные и сушильные машины
- Кондиционеры (сплит-системы, оконные)
- Газовые и электрические плиты
- Телевизоры и большие мониторы (от 32 дюймов)
- Посудомоечные машины
- Микроволновые печи
- Водонагреватели (бойлеры)
- Пылесосы
- Мебель (диваны, кровати, шкафы, столы, стулья, стеллажи)
- Ковры и большие паласы
- Крупная кухонная техника

Мы НЕ покупаем:
- Смартфоны, планшеты, ноутбуки, компьютеры и комплектующие
- Мелкую электронику (наушники, джойстики, зарядки, кабели, умные часы, камеры)
- Одежду, обувь, аксессуары
- Инструменты, запчасти, комплектующие
- Детские товары (коляски, автокресла)
- Спортивный инвентарь
- Велосипеды, самокаты
- Книги, игрушки, игры
"""

# Condition definitions are explicit so the model makes consistent choices
_CONDITION_GUIDE = """
Определение состояния — выбери ОДНО:
- "new"      : запечатанный, неиспользованный, в оригинальной упаковке
- "like_new" : использовался очень мало, видимых дефектов нет, всё работает
- "good"     : заметные следы использования (царапины, потёртости), но полностью рабочий
- "fair"     : явные дефекты (вмятины, трещины корпуса, частично не работает), но основная функция есть
- "damaged"  : не работает или требует серьёзного ремонта для использования
- "unknown"  : из описания невозможно определить состояние
"""


def _build_extract_system() -> str:
    return f"""Ты анализируешь объявление о продаже б/у товара в Ташкенте, Узбекистан.
Тебе дано оригинальное описание от продавца И результаты поиска с актуальными рыночными ценами.
Описание может быть на русском, узбекском или смешанном языке — анализируй как есть.

{_CATEGORY_DESCRIPTION}

{_CONDITION_GUIDE}

Верни ТОЛЬКО валидный JSON-объект с этими полями:

{{
  "product_name": "чёткое описательное название товара НА РУССКОМ языке",
  "brand": "бренд или null",
  "model": "модель или null",
  "condition": одно из ["new", "like_new", "good", "fair", "damaged", "unknown"],
  "is_in_category": true или false,
  "market_price_uzs": целое число UZS или null,
  "price_confidence": одно из ["high", "medium", "low", "none"],
  "price_notes": "одно короткое предложение о том, как определена цена, или null",
  "needs_repair": true или false,
  "repair_type": "краткое описание необходимого ремонта, или null",
  "repair_cost_uzs": целое число UZS или null
}}

Правила:
- product_name: ВСЕГДА на русском языке, даже если описание на узбекском.
- is_in_category: true только если товар явно входит в наш список покупки.
  При сомнении для БЫТОВОЙ ТЕХНИКИ И МЕБЕЛИ — ставь true.
  При сомнении для электроники, одежды, транспорта — ставь false.
- market_price_uzs: медианная цена перепродажи в рабочем состоянии в Ташкенте.
  Основывай на результатах поиска. null если данных нет.
- Если в результатах поиска цены в USD — конвертируй: 1 USD = {_USD_RATE} UZS.
- price_confidence:
    "high"   = 3+ совпадающих объявления
    "medium" = 1-2 объявления
    "low"    = экстраполяция или очень мало данных
    "none"   = данных не найдено
- repair_cost_uzs: реалистичная оценка ремонта в ташкентском сервисе. null если ремонт не нужен.
- needs_repair: true если из описания явно следует неисправность или повреждение.
- Все цены ТОЛЬКО в UZS.
- Никакого markdown, никаких комментариев — только чистый JSON."""


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
    ) or "Результаты поиска не найдены."

    user_msg = f"Описание товара от продавца:\n{text}\n\nРезультаты поиска цен:\n{search_block}"
    raw = await _call(
        Config.MAIN_MODEL,
        _build_extract_system(),
        user_msg,
        session,
        max_tokens=600,
    )
    result = _parse_json(raw, "extract model")
    logger.debug(f"[llm] extracted: {result}")
    return result  # type: ignore


# ---------------------------------------------------------------------------
# Step 3 — cheap model: generate repair search queries
# ---------------------------------------------------------------------------

_REPAIR_QUERY_SYSTEM = """Ты генерируешь поисковые запросы НА РУССКОМ ЯЗЫКЕ \
для поиска стоимости ремонта конкретной неисправности в Ташкенте, Узбекистан.

Верни ТОЛЬКО JSON-массив из 2 строк. Запросы должны:
- быть на русском языке
- содержать конкретный тип ремонта и название устройства
- содержать "Ташкент" или "цена" или "сколько стоит"

Пример для repair_type="замена подшипника", product="стиральная машина":
["замена подшипника стиральная машина цена Ташкент", "ремонт стиральной машины подшипник сколько стоит Узбекистан"]

Никакого markdown, только JSON-массив."""


async def get_repair_search_queries(
    repair_type: str,
    product_name: str,
    session: aiohttp.ClientSession,
) -> list[str]:
    text = f"Тип ремонта: {repair_type}\nУстройство: {product_name}"
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
# Step 4 — extract ONLY repair cost (focused second pass, saves tokens)
# ---------------------------------------------------------------------------

_REPAIR_EXTRACT_SYSTEM = f"""Ты определяешь стоимость ремонта б/у техники в Ташкенте.
Тебе дан тип неисправности и результаты поиска по ремонтным мастерским.

Верни ТОЛЬКО валидный JSON-объект:
{{
  "repair_cost_uzs": целое число UZS или null,
  "repair_notes": "одно предложение об источнике оценки, или null"
}}

Правила:
- repair_cost_uzs: реалистичная средняя цена ремонта в ташкентском сервисе.
- Если в результатах цены в USD — конвертируй: 1 USD = {_USD_RATE} UZS.
- null если данных недостаточно для оценки.
- Никакого markdown — только чистый JSON."""


async def extract_repair_cost(
    repair_type: str,
    product_name: str,
    repair_search_results: list[dict],
    session: aiohttp.ClientSession,
) -> dict:
    """
    Focused second pass — only extracts repair cost from repair-specific search results.
    Much cheaper than re-running the full extract_item prompt.
    """
    search_block = "\n\n".join(
        f"[{i + 1}] {r['title']}\n{r['snippet']}"
        for i, r in enumerate(repair_search_results)
        if r.get("title") or r.get("snippet")
    ) or "Результаты поиска не найдены."

    user_msg = (
        f"Устройство: {product_name}\n"
        f"Тип ремонта: {repair_type}\n\n"
        f"Результаты поиска по ремонту:\n{search_block}"
    )
    raw = await _call(
        Config.QUERY_MODEL,  # cheap model is enough for this simple extraction
        _REPAIR_EXTRACT_SYSTEM,
        user_msg,
        session,
        max_tokens=150,
    )
    result = _parse_json(raw, "repair extract model")
    logger.debug(f"[llm] repair cost extracted: {result}")
    return result  # type: ignore


# ---------------------------------------------------------------------------
# Shared JSON parser
# ---------------------------------------------------------------------------

def _parse_json(raw: str, context: str) -> dict | list:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[llm] invalid JSON from {context}: {e} | raw={raw[:300]}")
        raise RuntimeError(f"Invalid JSON from {context}: {e}\nRaw: {raw}")