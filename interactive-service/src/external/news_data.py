from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

log = logging.getLogger(__name__)

_FMP_NEWS_URL = "https://financialmodelingprep.com/api/v3/stock_news"


def _fetch_news_sync(symbols: List[str], api_key: str, max_per_stock: int) -> Dict[str, list]:
    """Synchronous FMP news fetch — called via asyncio.to_thread()."""
    if not api_key:
        return {sym: [] for sym in symbols}

    try:
        import requests
    except ImportError:
        log.warning("requests not installed — news_catalysts will be empty")
        return {sym: [] for sym in symbols}

    by_sym: Dict[str, list] = {sym: [] for sym in symbols}
    try:
        resp = requests.get(
            _FMP_NEWS_URL,
            params={
                "tickers": ",".join(symbols),
                "limit":   max_per_stock * len(symbols),
                "apikey":  api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json()
        if isinstance(items, list):
            for item in items:
                sym = item.get("symbol", "")
                if sym in by_sym and len(by_sym[sym]) < max_per_stock:
                    by_sym[sym].append({
                        "headline":     item.get("title", ""),
                        "source":       item.get("site", ""),
                        "published_at": item.get("publishedDate", ""),
                        "url":          item.get("url", ""),
                    })
        else:
            log.warning("FMP news API returned unexpected format: %s", type(items))
    except Exception as e:
        log.warning("FMP news fetch failed: %s", e)

    return by_sym


async def fetch_news_catalysts(
    symbols: List[str],
    api_key: str,
    max_per_stock: int = 3,
) -> Dict[str, list]:
    """Fetch recent news headlines for all symbols via FMP API."""
    if not symbols or not api_key:
        return {sym: [] for sym in symbols}
    return await asyncio.to_thread(_fetch_news_sync, symbols, api_key, max_per_stock)
