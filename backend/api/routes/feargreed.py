from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feargreed", tags=["feargreed"])

_CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com",
}

_RATING_LABELS = {
    "extreme_fear": "Extreme Fear",
    "fear": "Fear",
    "neutral": "Neutral",
    "greed": "Greed",
    "extreme_greed": "Extreme Greed",
}


def _label(rating: str) -> str:
    return _RATING_LABELS.get(rating.lower().replace(" ", "_"), rating.title())


async def _fetch_cnn() -> dict:
    async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as client:
        r = await client.get(_CNN_URL)
        r.raise_for_status()
        return r.json()


@router.get("")
async def get_fear_greed() -> dict:
    """Return the current CNN Fear & Greed index score."""
    try:
        data = await _fetch_cnn()
        fg = data["fear_and_greed"]
        return {
            "score": round(fg["score"]),
            "label": _label(fg["rating"]),
            "timestamp": fg["timestamp"],
            "stale": False,
        }
    except Exception as exc:
        logger.exception("CNN Fear & Greed fetch failed")
        return {"error": str(exc)}


@router.get("/history")
async def get_fear_greed_history(days: int = Query(default=30, ge=1, le=365)) -> list | dict:
    """Return historical CNN Fear & Greed scores for the last N days."""
    try:
        data = await _fetch_cnn()
        entries = data["fear_and_greed_historical"]["data"]
        # Each entry: {"x": ms_timestamp, "y": score, "rating": str}
        # CNN returns ~2 years of data; slice to requested days from the end
        sliced = entries[-days:]
        return [
            {
                "date": datetime.fromtimestamp(e["x"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
                "score": round(e["y"]),
                "label": _label(e["rating"]),
            }
            for e in sliced
        ]
    except Exception as exc:
        logger.exception("CNN Fear & Greed history fetch failed")
        return {"error": str(exc)}
