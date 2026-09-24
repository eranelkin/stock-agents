from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from ib_async import IB

from src.config.loader import PacingConfig
from src.ib.ratelimiter import limiter

log = logging.getLogger(__name__)

_IB_DATE_FMT = "%Y%m%d-%H:%M:%S"


async def fetch_news_providers(ib: IB) -> List[str]:
    """Return provider codes this IB account is entitled to. Empty if no subscription."""
    try:
        providers = await ib.reqNewsProvidersAsync()
    except Exception as e:
        log.warning("reqNewsProviders failed: %s", e)
        return []

    codes = [p.code for p in providers if getattr(p, "code", "")]
    if not codes:
        log.warning("No IB news providers entitled on this account — IB news will be empty")
    else:
        log.info("IB news providers: %s", ",".join(codes))
    return codes


async def fetch_ib_news_for_symbol(
    ib: IB,
    con_id: int,
    symbol: str,
    provider_codes: List[str],
    lookback_hours: int = 72,
    max_results: int = 3,
    timeout: float = 45.0,
) -> list:
    """Fetch recent headlines for one contract via IB's native historical news,
    filtered server-side to lookback_hours. Returns the same item shape as the
    FMP news_catalysts fetch: {headline, source, published_at, url}."""
    if not provider_codes or not con_id:
        return []

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=lookback_hours)
    try:
        result = await asyncio.wait_for(
            ib.reqHistoricalNewsAsync(
                con_id,
                ",".join(provider_codes),
                start.strftime(_IB_DATE_FMT),
                end.strftime(_IB_DATE_FMT),
                max_results,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning("%s: reqHistoricalNews timed out after %.0fs", symbol, timeout)
        return []
    except Exception as e:
        log.warning("%s: reqHistoricalNews failed: %s", symbol, e)
        return []

    headlines = getattr(result, "headlines", None) if result is not None else None
    if not headlines:
        return []

    items = []
    for h in headlines[:max_results]:
        items.append({
            "headline": h.headline or "",
            "source": h.providerCode or "",
            "published_at": h.time.isoformat() if h.time else None,
            "url": None,
        })
    return items


async def fetch_ib_news_for_all(
    ib: IB,
    con_ids: Dict[str, int],
    provider_codes: List[str],
    pacing: PacingConfig,
    lookback_hours: int = 72,
    max_results: int = 3,
    concurrency: int = 3,
) -> Dict[str, list]:
    """Fetch IB-native news for all symbols concurrently, sharing the historical
    rate limiter's budget with other IB historical-data requests."""
    if not provider_codes:
        return {sym: [] for sym in con_ids}

    semaphore = asyncio.Semaphore(concurrency)

    async def worker(symbol: str, con_id: int) -> tuple[str, list]:
        async with semaphore:
            await limiter.acquire(min_gap=pacing.historical_delay_seconds)
            items = await fetch_ib_news_for_symbol(
                ib, con_id, symbol, provider_codes,
                lookback_hours=lookback_hours, max_results=max_results,
                timeout=pacing.historical_request_timeout_seconds,
            )
            return symbol, items

    tasks = [worker(sym, con_id) for sym, con_id in con_ids.items()]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: Dict[str, list] = {}
    for sym, res in zip(con_ids.keys(), task_results):
        if isinstance(res, Exception):
            log.error("%s: IB news worker failed: %s", sym, res)
            results[sym] = []
        else:
            _, items = res
            results[sym] = items

    log.info("Fetched IB news for %d symbols", len(con_ids))
    return results
