import os
import time
import base64

from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from product_processing import vision
from pydantic import BaseModel, Field

from config import Config
from product_processing.llm import (
    get_search_queries,
    extract_item,
    get_repair_search_queries,
    extract_repair_cost,
)
from product_processing.search import multi_search
from product_processing.logger import setup_logging, get_logger

_session: aiohttp.ClientSession | None = None

os.makedirs("logs", exist_ok=True)
setup_logging(log_file="logs/pricer.log")
logger = get_logger("pricer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session
    logger.info("[pricer] Starting Item Pricer microservice")
    _session = aiohttp.ClientSession()
    yield
    await _session.close()
    logger.info("[pricer] Shutting down")

app = FastAPI(
    title="Item Pricer",
    description="Extracts structured item data and calculates profit from UZS prices",
    version="2.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="Raw item description")
    desired_price: str = Field(..., description="Seller's asking price (not normalized)")
    images: list[str] = Field(default=[], description="Base64-encoded JPEG images (optional)")

class AnalyzeResponse(BaseModel):
    processing_time_ms: int

    # Item identity
    product_name: str | None
    brand: str | None
    model: str | None
    condition: str | None

    # Category gate
    is_in_category: bool

    # Pricing — all UZS
    desired_price_uzs: int
    market_price_uzs: int | None
    fast_sell_price_uzs: int | None
    repair_cost_uzs: int | None
    profit_uzs: int | None
    price_confidence: str | None
    price_notes: str | None

    # Repair
    needs_repair: bool
    repair_type: str | None

    # Vision
    vision_used: bool 
    vision_confidence: str | None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    start = time.monotonic()
    session = _session
    if not session:
        return {}

    # Stage 0: vision
    vision_context = None
    if req.images:
        try:
            image_bytes_list = [base64.b64decode(img) for img in req.images]
            vision_context = await vision.analyze_images(image_bytes_list, session)
            if vision_context:
                logger.info(f"[pipeline] vision complete confidence={vision_context.confidence}")
            else:
                logger.info("[pipeline] vision returned None, continuing text-only")
        except Exception as e:
            logger.warning(f"[pipeline] vision failed: {e}, continuing text-only")

    # Stage 1: search queries — include vision output if available
    vision_block = vision_context.to_text_block() if vision_context else ""
    query_prompt = f"CLIENT DESCRIPTION:{req.text}"
    if vision_block:
        query_prompt += f"\nVISION MODEL ANALYSIS:\n{vision_block}"
    try:
        queries = await get_search_queries(query_prompt, session)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Stage 2: market price search
    search_results = await multi_search(queries, session)

    # Stage 3: extract structured item data
    try:
        item = await extract_item(req.text, search_results, session, vision_context, req.desired_price)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Stage 4: repair cost — focused second-pass search, only if needed
    if item.get("needs_repair") and item.get("repair_type"):
        try:
            repair_queries = await get_repair_search_queries(
                item["repair_type"],
                item.get("product_name") or req.text,
                session,
            )
            repair_results = await multi_search(repair_queries, session)
            repair_data = await extract_repair_cost(
                repair_type=item["repair_type"],
                product_name=item.get("product_name") or req.text,
                repair_search_results=repair_results,
                session=session,
            )

            logger.info(
                f"[pipeline] repair extract: cost={repair_data.get('repair_cost_uzs')} "
                f"notes={repair_data.get('repair_notes', '')[:120]}"
            )

            # Patch repair cost only if the second pass found something concrete.
            # If it returns null, keep the first-pass estimate (may also be null — that's fine).
            if repair_data.get("repair_cost_uzs") is not None:
                item["repair_cost_uzs"] = repair_data["repair_cost_uzs"]

            # Always surface repair reasoning in price_notes so admin sees it
            if repair_data.get("repair_notes"):
                existing = item.get("price_notes") or ""
                item["price_notes"] = f"{existing} | Ремонт: {repair_data['repair_notes']}".strip(" |")

        except Exception as e:
            logger.warning(f"[pipeline] repair cost extraction failed: {e}")

    # ---------------------------------------------------------------------------
    # Profit calculation — done AFTER repair patch so the cost is final
    # ---------------------------------------------------------------------------
    market_uzs: int | None = item.get("market_price_uzs")
    repair_uzs: int | None = item.get("repair_cost_uzs")
    fast_sell_uzs: int | None = None
    profit_uzs: int | None = None
    desired_price = int(item.get("desired_price_uzs") or 0)

    if market_uzs is not None:
        fast_sell_uzs = int(market_uzs * Config.FAST_SELL_RATIO)
        repair = repair_uzs or 0
        profit_uzs = fast_sell_uzs - desired_price - repair
        logger.info(
            f"[pipeline] profit calc: market={market_uzs} fast_sell={fast_sell_uzs} "
            f"desired={desired_price} repair={repair} profit={profit_uzs}"
        )
    else:
        logger.info(
            f"[pipeline] no market price — profit not calculated "
            f"(confidence={item.get('price_confidence')!r})"
        )

    elapsed = int((time.monotonic() - start) * 1000)

    return AnalyzeResponse(
        processing_time_ms=elapsed,
        product_name=item.get("product_name"),
        brand=item.get("brand"),
        model=item.get("model"),
        condition=item.get("condition"),
        is_in_category=bool(item.get("is_in_category", True)),
        desired_price_uzs=desired_price,
        market_price_uzs=market_uzs,
        fast_sell_price_uzs=fast_sell_uzs,
        repair_cost_uzs=repair_uzs,
        profit_uzs=profit_uzs,
        price_confidence=item.get("price_confidence"),
        price_notes=item.get("price_notes"),
        needs_repair=bool(item.get("needs_repair", False)),
        repair_type=item.get("repair_type"),
        vision_used=vision_context is not None,
        vision_confidence=vision_context.confidence if vision_context else None,
    )