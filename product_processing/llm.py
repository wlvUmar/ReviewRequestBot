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
from product_processing.logger import get_logger

logger = get_logger(__name__)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from product_processing.vision import VisionContext

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
        "Authorization": f"Bearer {Config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    logger.debug(f"[llm] calling model={model} max_tokens={max_tokens}")
    try:
        async with session.post(
            Config.LLM_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT),
        ) as resp:
            data = await resp.json()
    except Exception as e:
        logger.error(f"[llm] call failed model={model}: {e}")
        raise RuntimeError(f"LLM call failed: {e}")

    if not isinstance(data, dict) or "choices" not in data:
        # e.g. {"error": {"message": "No auth credentials found", "code": 401}} from OpenRouter
        err = data.get("error") if isinstance(data, dict) else data
        logger.error(f"[llm] OpenRouter returned no choices for model={model}: {str(err)[:300]}")
        raise RuntimeError(f"OpenRouter error: {str(err)[:200]}")

    raw = data["choices"][0]["message"]["content"].strip()
    logger.debug(f"[llm] raw response ({len(raw)} chars): {raw[:200]}")
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ---------------------------------------------------------------------------
# Step 1 — generate search queries
# ---------------------------------------------------------------------------

_QUERY_SYSTEM = """Ты генерируешь поисковые запросы для поиска актуальных цен на б/у товары в Ташкенте.

Правила:
- Верни ТОЛЬКО JSON-массив из 2-3 строк.
- Каждый запрос должен быть конкретным — использовать точное название товара как его ищут на OLX.uz.
- ВСЕГДА включай "olx.uz" в один из запросов — это главная площадка для мебели и техники в Ташкенте.
- Для мебели: используй точное русское название (горка, диван-кровать, шкаф-купе, кухонный гарнитур и т.д.).
  НЕ используй широкие категории типа "мебель" или "шкаф" если известно точное название.
- Для техники: включай бренд и модель если известны.
- Запросы на русском языке.

Примеры:
  Товар "горка":
  ["горка мебель б/у цена Ташкент olx.uz", "горка витрина купить Ташкент", "горка мебель Ташкент цена сум"]

  Товар "Samsung холодильник двухкамерный":
  ["Samsung холодильник б/у цена Ташкент olx.uz", "холодильник Samsung 350L Ташкент", "Samsung холодильник бу Узбекистан цена"]

  Товар "диван-кровать угловой":
  ["диван-кровать угловой б/у цена Ташкент olx.uz", "угловой диван Ташкент купить б/у", "диван раскладной Ташкент цена сум"]

Никакого markdown, только JSON-массив."""


async def get_search_queries(text: str, session: aiohttp.ClientSession) -> list[str]:
    logger.debug(f"[llm] generating search queries for: {text[:100]}")
    raw = await _call(Config.QUERY_MODEL, _QUERY_SYSTEM, text, session, max_tokens=200)
    result = _parse_json(raw, "query model")
    if not isinstance(result, list):
        logger.warning(f"[llm] query model returned non-list: {result}")
        return [text]
    queries = [str(q) for q in result if q][:3]
    logger.debug(f"[llm] generated queries: {queries}")
    return queries


# ---------------------------------------------------------------------------
# Step 2 — extract structured item data
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
- Мебель (диваны, кровати, шкафы, горки, гарнитуры, столы, стулья, стеллажи, комоды, тумбы)
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

_CONDITION_GUIDE = """
Состояние — выбери ОДНО:
- "new"      : запечатанный, неиспользованный, в оригинальной упаковке
- "like_new" : использовался очень мало, видимых дефектов нет
- "good"     : заметные следы использования, но полностью рабочий/функциональный
- "fair"     : явные дефекты (вмятины, трещины, порванная обивка), но основная функция есть
- "damaged"  : не работает или требует серьёзного ремонта
- "unknown"  : из описания невозможно определить
"""

_FURNITURE_PRICING_GUIDE = """
ВАЖНО — ценообразование мебели в Ташкенте:
Большинство мебели в Ташкенте изготовлена местными мебельщиками (не брендовая).
Цены сильно варьируются в зависимости от размера, материала и состояния.
Ориентируйся ТОЛЬКО на результаты поиска с OLX.uz и местных площадок.
НЕ используй цены с российских, европейских или международных сайтов — они нерелевантны.
Если в результатах поиска нет конкретных объявлений с ценами из Ташкента — ставь market_price_uzs: null и price_confidence: "none".
Лучше вернуть null чем угадывать цену на основе нерелевантных данных.
"""


def _build_extract_system() -> str:
    return f"""Ты анализируешь объявление о продаже б/у товара в Ташкенте, Узбекистан.
Тебе дано описание от продавца И результаты поиска с актуальными ценами.
Описание может быть на русском, узбекском или смешанном языке.

{_CATEGORY_DESCRIPTION}

{_CONDITION_GUIDE}

{_FURNITURE_PRICING_GUIDE}

Верни ТОЛЬКО валидный JSON-объект:

{{
  "product_name": "точное название товара НА РУССКОМ (используй местные названия: горка, диван-кровать, кухонный гарнитур и т.д.)",
  "brand": "бренд или null",
  "model": "модель или null",
  "condition": одно из ["new", "like_new", "good", "fair", "damaged", "unknown"],
  "is_in_category": true или false,
  "market_price_uzs": целое число UZS или null,
  "price_confidence": одно из ["high", "medium", "low", "none"],
  "price_notes": "короткое предложение об источнике цены, или null",
  "needs_repair": true или false,
  "repair_type": "описание ремонта или null",
  "repair_cost_uzs": целое число UZS или null,
"desired_price_uzs": нормализуй client_asked_price из строки в целое число UZS.

Примеры:
"700 тыс" → 700000
"1.5 млн" → 1500000
"50" → 50
"200k" → 200000

Если содержит "usd" → умножь на {_USD_RATE}.
Если пусто/невалидно → 0.

Сохраняй намерение пользователя. Не изменяй цену на основе рыночной стоимости товара и не пытайся её оценивать заново.

Разрешается исправлять только очевидные ошибки масштаба при вводе (лишние или пропущенные нули), если из контекста объявления это практически однозначно. Например, телевизор за "50000000" может означать "5000000", а холодильник за "50" может означать "50000". В таких случаях скорректируй только порядок величины, сохранив исходные цифры пользователя.

Никогда не заменяй цену на предполагаемую рыночную цену товара. Если ошибка не очевидна — используй число как указано пользователем.
}}

Правила:
- product_name: ВСЕГДА на русском, используй точное местное название (горка, а не шкаф).
- is_in_category: true если товар входит в наш список. Для мебели и бытовой техники при сомнении — true.
- market_price_uzs: медианная цена б/у в Ташкенте из результатов поиска.
  Если в поиске нет объявлений с ценами из Ташкента/Узбекистана — верни null.
  Не используй цены с нерелевантных рынков.
- Если цены в результатах в USD — конвертируй: 1 USD = {_USD_RATE} UZS.
- price_confidence:
    "high"   = 3+ совпадающих объявления с OLX.uz или местных площадок
    "medium" = 1-2 объявления
    "low"    = экстраполяция, мало данных
    "none"   = данных из Ташкента не найдено — обязательно ставь null для market_price_uzs
- needs_repair: true если из описания или фото следует неисправность.
- repair_cost_uzs: null если ремонт не нужен или неизвестен.
- Все цены ТОЛЬКО в UZS.
- Никакого markdown — только чистый JSON."""


async def extract_item(
    text: str,
    search_results: list[dict],
    session: aiohttp.ClientSession,
    vision_context: "VisionContext | None",
    desired_price: str,
) -> dict:
    logger.debug(f"[llm] extracting item text={text[:100]!r} search_results={len(search_results)}")

    search_block = "\n\n".join(
        f"[{i + 1}] {r['title']}\n{r['snippet']}"
        for i, r in enumerate(search_results)
        if r.get("title") or r.get("snippet")
    ) or "Результаты поиска не найдены."

    user_msg = (
        f"Описание товара от продавца:\n{text}\n\n"
        f"Результаты поиска цен:\n{search_block}\n"
        f"client_asked_price: {desired_price}"
    )
    if vision_context:
        user_msg += f"\n\n{vision_context.to_text_block()}"

    raw = await _call(Config.MAIN_MODEL, _build_extract_system(), user_msg, session, max_tokens=600)
    result = _parse_json(raw, "extract model")
    logger.debug(f"[llm] extracted: {result}")
    return result  # type: ignore


# ---------------------------------------------------------------------------
# Step 3 — repair search queries
# ---------------------------------------------------------------------------

_REPAIR_QUERY_SYSTEM = """Ты генерируешь поисковые запросы НА РУССКОМ ЯЗЫКЕ \
для поиска стоимости ремонта в Ташкенте, Узбекистан.

Верни ТОЛЬКО JSON-массив из 2 строк. Запросы должны:
- содержать конкретный тип ремонта и название устройства
- содержать "Ташкент" или "цена" или "сколько стоит"

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
# Step 4 — repair cost extraction
# ---------------------------------------------------------------------------

_REPAIR_EXTRACT_SYSTEM = f"""Ты определяешь стоимость ремонта б/у техники в Ташкенте.
Тебе дан тип неисправности и результаты поиска по ремонтным мастерским.

Верни ТОЛЬКО валидный JSON-объект:
{{
  "repair_cost_uzs": целое число UZS или null,
  "repair_notes": "объясни откуда взята цена: какое объявление/источник, диапазон найденных цен, почему выбрана эта сумма. Если данных нет — объясни почему null."
}}

Правила:
- repair_cost_uzs: средняя реалистичная цена ремонта в ташкентском сервисе.
- Используй ТОЛЬКО цены из результатов поиска. Не придумывай цену.
- Если в результатах нет конкретных цен на этот тип ремонта — верни null.
- Если цены в USD — конвертируй: 1 USD = {_USD_RATE} UZS.
- repair_notes ОБЯЗАТЕЛЕН — всегда объясняй своё решение, даже если вернул null.
- Только чистый JSON."""


async def extract_repair_cost(
    repair_type: str,
    product_name: str,
    repair_search_results: list[dict],
    session: aiohttp.ClientSession,
) -> dict:
    # Skip the LLM call entirely if search came back empty — saves tokens and
    # avoids the model hallucinating a repair cost from zero data.
    actual_results = [r for r in repair_search_results if r.get("snippet", "").strip()]
    if not actual_results:
        logger.debug("[llm] repair search empty — skipping extract, returning null")
        return {
            "repair_cost_uzs": None,
            "repair_notes": "Поиск не вернул результатов по стоимости ремонта в Ташкенте.",
        }

    search_block = "\n\n".join(
        f"[{i + 1}] {r['title']}\n{r['snippet']}"
        for i, r in enumerate(actual_results)
    )

    user_msg = (
        f"Устройство: {product_name}\n"
        f"Тип ремонта: {repair_type}\n\n"
        f"Результаты поиска:\n{search_block}"
    )
    raw = await _call(Config.QUERY_MODEL, _REPAIR_EXTRACT_SYSTEM, user_msg, session, max_tokens=200)
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