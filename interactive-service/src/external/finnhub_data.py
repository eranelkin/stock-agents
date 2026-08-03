from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_QUOTE_URL = "https://finnhub.io/api/v1/quote"


def _fetch_finnhub_sync(symbols: List[str], api_key: str) -> Dict[str, Optional[float]]:
    """Synchronous Finnhub quote fetch — called via asyncio.to_thread().

    Uses the /quote endpoint which returns current session volume (v).
    Before 9:30 AM ET this accumulates only pre-market trades.
    Free tier: 60 calls/min — 40 symbols completes in well under 1 minute.
    """
    try:
        import requests
    except ImportError:
        log.warning("requests not installed — Finnhub pre_market_volume unavailable")
        return {sym: None for sym in symbols}

    results: Dict[str, Optional[float]] = {sym: None for sym in symbols}

    for sym in symbols:
        try:
            resp = requests.get(
                _QUOTE_URL,
                params={"symbol": sym, "token": api_key},
                timeout=10,
            )
            if resp.status_code == 401:
                log.error(
                    "Finnhub API returned 401 Unauthorized — check finnhub_api_key in settings.yaml"
                )
                return results
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("v")
            if raw is not None:
                try:
                    vol = float(raw)
                    if vol > 0:
                        results[sym] = vol
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            log.warning("Finnhub quote fetch failed for %s: %s", sym, e)

    found = sum(1 for v in results.values() if v is not None)
    log.info("Finnhub pre-market volume: %d / %d symbols populated", found, len(symbols))
    return results


async def fetch_finnhub_premarket_volume(
    symbols: List[str],
    api_key: str,
) -> Dict[str, Optional[float]]:
    """Fetch current session volume for all symbols via Finnhub quote endpoint."""
    if not symbols or not api_key:
        return {sym: None for sym in symbols}
    return await asyncio.to_thread(_fetch_finnhub_sync, symbols, api_key)
