from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from ib_async import IB, Contract

from src.config.loader import PacingConfig
from src.ib.ratelimiter import limiter

log = logging.getLogger(__name__)


@dataclass
class VolumeProfile:
    poc: Optional[float]               # Point of Control — price bin with highest volume
    vah: Optional[float]               # Value Area High  — upper bound of 70% value area
    val: Optional[float]               # Value Area Low   — lower bound of 70% value area
    lookback_sessions: int


async def fetch_volume_profile(
    ib: IB,
    contract: Contract,
    lookback_sessions: int = 3,
    timeout: float = 45.0,
) -> VolumeProfile:
    """Compute Volume Profile POC, VAH, VAL via IB's reqHistogramData.

    IB returns a list of HistogramData(price, count) buckets. `count` is a
    tick-count proxy for volume. VAH/VAL enclose 70% of total volume around POC.
    timeout: max seconds to wait before treating this request as failed — guards
    against IB data-farm hangs blocking the whole batch indefinitely (asyncio.gather
    waits for every worker, so one stuck request would otherwise stall all others).
    """
    sym = contract.symbol
    empty = VolumeProfile(None, None, None, lookback_sessions)
    prev_raise = ib.RaiseRequestErrors
    ib.RaiseRequestErrors = True
    try:
        histogram = await asyncio.wait_for(
            ib.reqHistogramDataAsync(
                contract,
                useRTH=False,
                period=f"{lookback_sessions} days",
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning("%s: reqHistogramData timed out after %.0fs", sym, timeout)
        return empty
    except Exception as e:
        log.warning("%s: reqHistogramData failed: %s", sym, e)
        return empty
    finally:
        ib.RaiseRequestErrors = prev_raise

    if not histogram:
        log.warning("%s: reqHistogramData returned empty histogram — check IB data subscription or contract qualification", sym)
        return empty

    total = sum(h.count for h in histogram)
    if total == 0:
        return empty

    # POC — bin with highest tick count
    poc_bin = max(histogram, key=lambda h: h.count)
    poc = poc_bin.price

    # Value Area — accumulate 70% of total outward from POC
    target      = total * 0.70
    accumulated = poc_bin.count
    sorted_bins = sorted(histogram, key=lambda h: h.price)
    poc_idx     = next(i for i, h in enumerate(sorted_bins) if h.price == poc)

    lo_idx, hi_idx = poc_idx, poc_idx
    while accumulated < target:
        expand_lo = lo_idx > 0
        expand_hi = hi_idx < len(sorted_bins) - 1
        if not expand_lo and not expand_hi:
            break
        lo_vol = sorted_bins[lo_idx - 1].count if expand_lo else 0
        hi_vol = sorted_bins[hi_idx + 1].count if expand_hi else 0
        if lo_vol >= hi_vol and expand_lo:
            lo_idx     -= 1
            accumulated += lo_vol
        elif expand_hi:
            hi_idx     += 1
            accumulated += hi_vol
        else:
            lo_idx     -= 1
            accumulated += lo_vol

    return VolumeProfile(
        poc=sorted_bins[poc_idx].price,
        vah=sorted_bins[hi_idx].price,
        val=sorted_bins[lo_idx].price,
        lookback_sessions=lookback_sessions,
    )


async def fetch_all_volume_profiles(
    ib: IB,
    contracts: List[Contract],
    pacing: PacingConfig,
    lookback_sessions: int = 3,
    concurrency: int = 3,
) -> Dict[str, VolumeProfile]:
    """Fetch Volume Profiles for all contracts concurrently with rate limiting."""
    semaphore = asyncio.Semaphore(concurrency)
    timeout = pacing.historical_request_timeout_seconds

    async def worker(contract: Contract) -> tuple[str, VolumeProfile]:
        async with semaphore:
            await limiter.acquire(min_gap=pacing.historical_delay_seconds)
            vp = await fetch_volume_profile(ib, contract, lookback_sessions, timeout=timeout)
            return contract.symbol, vp

    tasks = [worker(c) for c in contracts]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: Dict[str, VolumeProfile] = {}
    for i, res in enumerate(task_results):
        if isinstance(res, Exception):
            log.error("%s: volume profile worker failed: %s", contracts[i].symbol, res)
        elif res:
            symbol, vp = res
            results[symbol] = vp

    log.info("Fetched volume profiles for %d symbols", len(results))
    return results
