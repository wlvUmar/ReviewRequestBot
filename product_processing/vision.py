"""
product_processing/vision.py
Vision model analysis of product photos via OpenRouter
"""

import json
import base64
import hashlib
import time
import asyncio
import aiohttp
from config import Config
from product_processing.provider import complete

from product_processing.logger import get_logger

logger = get_logger(__name__)

_vision_cache: dict[str, tuple["VisionContext", float]] = {}
_CACHE_TTL = 3600


class VisionContext:
    """Structured extraction from product photos"""
    def __init__(
        self,
        category: str | None,
        subcategory: str | None,
        condition: str | None,
        visible_damage: str | None,
        materials: str | None,
        brand_guess: str | None,
        model_guess: str | None,
        confidence: str,
        raw_response: str,
    ):
        self.category = category
        self.subcategory = subcategory
        self.condition = condition
        self.visible_damage = visible_damage
        self.materials = materials
        self.brand_guess = brand_guess
        self.model_guess = model_guess
        self.confidence = confidence
        self.raw_response = raw_response

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "condition": self.condition,
            "visible_damage": self.visible_damage,
            "materials": self.materials,
            "brand_guess": self.brand_guess,
            "model_guess": self.model_guess,
            "confidence": self.confidence,
        }

    def to_text_block(self) -> str:
        """Format as a text block for injection into LLM prompts.
        Leads with category/subcategory since those are most useful for
        query generation and item extraction."""
        lines = ["--- Анализ фотографий товара ---"]
        # Category first — this is what the query generator needs most
        if self.category:
            cat = self.category
            if self.subcategory:
                cat += f" ({self.subcategory})"
            lines.append(f"Тип товара: {cat}")
        if self.brand_guess:
            lines.append(f"Бренд (предположительно): {self.brand_guess}")
        if self.model_guess:
            lines.append(f"Модель (предположительно): {self.model_guess}")
        if self.condition:
            lines.append(f"Состояние (по фото): {self.condition}")
        if self.visible_damage:
            lines.append(f"Видимые повреждения: {self.visible_damage}")
        if self.materials:
            lines.append(f"Материалы: {self.materials}")
        lines.append(f"Уверенность анализа: {self.confidence}")
        return "\n".join(lines)

    def __str__(self) -> str:
        """Fallback string representation — returns the text block.
        Prevents accidental f-string injection of the object address."""
        return self.to_text_block()


def _cache_key(image_bytes_list: list[bytes]) -> str:
    h = hashlib.sha256()
    for img in image_bytes_list:
        h.update(img)
    return h.hexdigest()


def _get_cached(key: str) -> "VisionContext | None":
    entry = _vision_cache.get(key)
    if entry:
        ctx, timestamp = entry
        if time.time() - timestamp < _CACHE_TTL:
            logger.debug("[vision] cache hit")
            return ctx
        _vision_cache.pop(key, None)
    return None


def _cache_result(key: str, ctx: "VisionContext") -> None:
    _vision_cache[key] = (ctx, time.time())


async def analyze_images(
    image_bytes_list: list[bytes],
    session: aiohttp.ClientSession,
) -> "VisionContext | None":
    if not image_bytes_list or not Config.VISION_API_KEY:
        return None

    cache_key = _cache_key(image_bytes_list)
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        logger.debug(f"[vision] calling vision model, images={len(image_bytes_list)}")
        try:
            raw_response = await complete(
                session,
                url=Config.VISION_URL,
                api_key=Config.VISION_API_KEY,
                model=Config.VISION_MODEL,
                system=_VISION_SYSTEM_PROMPT,
                user="Analyze these product photos and return the JSON object.",
                images_b64=[base64.b64encode(b).decode() for b in image_bytes_list[:4]],
                max_tokens=500,
                timeout=30,
            )
        except RuntimeError as e:
            logger.warning(f"[vision] model failed: {e}")
            return None
        logger.debug(f"[vision] raw response: {raw_response[:200]}")

        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
        raw_response = raw_response.strip()

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.warning(f"[vision] invalid JSON: {e}")
            return None

        ctx = VisionContext(
            category=parsed.get("category"),
            subcategory=parsed.get("subcategory"),
            condition=parsed.get("condition"),
            visible_damage=parsed.get("visible_damage"),
            materials=parsed.get("materials"),
            brand_guess=parsed.get("brand_guess"),
            model_guess=parsed.get("model_guess"),
            confidence=parsed.get("confidence", "unknown"),
            raw_response=raw_response,
        )

        _cache_result(cache_key, ctx)
        logger.info(f"[vision] analysis complete confidence={ctx.confidence} category={ctx.category!r}")
        return ctx

    except asyncio.TimeoutError:
        logger.warning("[vision] timeout (>20s)")
        return None
    except aiohttp.ClientError as e:
        logger.warning(f"[vision] connection error: {e}")
        return None
    except Exception as e:
        logger.warning(f"[vision] unexpected error: {e}", exc_info=True)
        return None


_VISION_SYSTEM_PROMPT = """You are analyzing product photos for a second-hand goods buyer in Tashkent, Uzbekistan.
Your job is to identify what the item actually IS — use the specific local name where it exists.

FURNITURE NAMING RULES (critical — these are commonly sold in Tashkent):
Use the exact Russian name that locals use when selling on OLX.uz:
- A tall display cabinet with glass doors and shelves (often with a bar section) → "горка" (NOT шкаф, NOT стеллаж)
- A wardrobe/closet for clothes → "шкаф-купе" (sliding doors) or "распашной шкаф" (hinged doors)
- A sofa that folds into a bed → "диван-кровать" or "угловой диван" if corner-shaped
- A simple sofa (no bed function) → "диван"
- A coffee table → "журнальный стол"
- A dining table → "обеденный стол"
- A kitchen corner bench set → "кухонный уголок"
- A TV unit/stand → "тумба под телевизор"
- A chest of drawers → "комод"
- A bookshelf/open shelving unit → "стеллаж"
- A bed frame → "кровать"
- A bunk bed → "двухъярусная кровать"
- Bedroom set (bed + wardrobe + dresser) → "спальный гарнитур"
- Living room set (wall unit + sofa) → "мебельная стенка" for the wall unit
- Kitchen furniture set → "кухонный гарнитур"

For carpets and rugs:
- A large floor carpet → "ковёр"
- A runner carpet → "ковровая дорожка"
- A small rug → "коврик"
- Note pile height and pattern type if visible (ворсовый/безворсовый, с орнаментом)

BRAND/MODEL for furniture and carpets:
- Most furniture in Tashkent is made by local carpenters with no brand name — brand_guess and model_guess should almost always be null
- Only set brand_guess if a well-known brand label is clearly visible (e.g. IKEA, Shatura)
- Never guess a brand from the style or color

Return ONLY a valid JSON object:
{
  "category": "specific item name in Russian using local terminology (e.g. горка, диван-кровать, кухонный гарнитур)",
  "subcategory": "additional detail if useful (e.g. угловой, с витриной, 3-секционный) or null",
  "condition": one of ["new", "like_new", "good", "fair", "damaged", "unknown"],
  "visible_damage": "describe visible damage in Russian, or null",
  "materials": "main visible materials in Russian (е.g. ДСП, МДФ, массив дерева, ткань, кожзам) or null",
  "brand_guess": "brand name only if clearly visible, otherwise null",
  "model_guess": "model only if clearly visible on a label, otherwise null",
  "confidence": one of ["high", "medium", "low"]
}

Condition guide:
- new: unused, in packaging
- like_new: minimal use, no visible defects
- good: normal wear (scratches, scuffs) but structurally sound and clean
- fair: clear defects (chips, cracks, stains, torn upholstery, significant discoloration)
- damaged: broken structurally, requires repair to be usable
- unknown: cannot determine from photos

Confidence guide:
- high: item type is clearly identifiable
- medium: item type is likely but some details unclear
- low: hard to identify the item type from these photos

No markdown, no explanation — only the JSON object."""