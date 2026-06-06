"""
product_processing/main.py — Item Pricer FastAPI service.

All prices are in UZS. Profit is calculated here in Python, not by the LLM.

Profit formula:
    fast_sell_price_uzs = market_price_uzs * FAST_SELL_RATIO
    profit_uzs          = fast_sell_price_uzs - desired_price_uzs - repair_cost_uzs

Filtering decisions (is_in_category, profit threshold) are made by the
caller (request_service.py), not here. This service just returns numbers.
"""

import time
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import Config
from product_processing.llm import get_search_queries, extract_item, get_repair_search_queries
from product_processing.search import multi_search

_session: aiohttp.ClientSession | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session
    _session = aiohttp.ClientSession()
    yield
    await _session.close()


app = FastAPI(
    title="Item Pricer",
    description="Extracts structured item data and calculates profit from UZS prices",
    version="2.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="Raw item description")
    desired_price_uzs: int = Field(..., description="Seller's asking price in UZS (already normalized)")


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
    fast_sell_price_uzs: int | None      # market * FAST_SELL_RATIO
    repair_cost_uzs: int | None
    profit_uzs: int | None               # fast_sell - desired - repair
    price_confidence: str | None
    price_notes: str | None

    # Repair
    needs_repair: bool
    repair_type: str | None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    start = time.monotonic()
    session = _session

    # Stage 1: generate search queries
    try:
        queries = await get_search_queries(req.text, session)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Stage 2: search for market prices
    search_results = await multi_search(queries, session)

    # Stage 3: extract structured item data
    try:
        item = await extract_item(req.text, search_results, session)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Stage 4: if repair needed, enrich with repair cost search
    if item.get("needs_repair") and item.get("repair_type"):
        try:
            repair_queries = await get_repair_search_queries(
                item["repair_type"],
                item.get("product_name") or req.text,
                session,
            )
            repair_results = await multi_search(repair_queries, session)
            if repair_results:
                item = await extract_item(req.text, search_results + repair_results, session)
        except Exception as e:
            import logging
            logging.getLogger("reviewrequestbot").warning(
                f"[pricer] repair search failed, using first extraction: {e}"
            )

    # ---------------------------------------------------------------------------
    # Profit calculation — pure Python math, no LLM involvement
    # ---------------------------------------------------------------------------
    market_uzs: int | None = item.get("market_price_uzs")
    repair_uzs: int | None = item.get("repair_cost_uzs")
    fast_sell_uzs: int | None = None
    profit_uzs: int | None = None

    if market_uzs is not None:
        fast_sell_uzs = int(market_uzs * Config.FAST_SELL_RATIO)
        repair = repair_uzs or 0
        profit_uzs = fast_sell_uzs - req.desired_price_uzs - repair

    elapsed = int((time.monotonic() - start) * 1000)

    return AnalyzeResponse(
        processing_time_ms=elapsed,
        product_name=item.get("product_name"),
        brand=item.get("brand"),
        model=item.get("model"),
        condition=item.get("condition"),
        is_in_category=bool(item.get("is_in_category", True)),  # default True = let through
        desired_price_uzs=req.desired_price_uzs,
        market_price_uzs=market_uzs,
        fast_sell_price_uzs=fast_sell_uzs,
        repair_cost_uzs=repair_uzs,
        profit_uzs=profit_uzs,
        price_confidence=item.get("price_confidence"),
        price_notes=item.get("price_notes"),
        needs_repair=bool(item.get("needs_repair", False)),
        repair_type=item.get("repair_type"),
    )


@app.get("/health")
async def health():
    return {"status": "ok"} 