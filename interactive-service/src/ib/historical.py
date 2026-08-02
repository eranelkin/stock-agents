from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import time as dtime
from typing import Dict, List, Optional

from ib_async import IB, BarData, Contract

from src.config.loader import PacingConfig
from src.ib.ratelimiter import limiter

log = logging.getLogger(__name__)

_BAR_SIZE = "1 day"

# Pre-market window boundaries (ET)
_PM_START = dtime(4, 0)   # 04:00
_PM_END   = dtime(9, 30)  # 09:30


# ── Rate limiter ───────────────────────────────────────────────────────────────
# A shared rate limiter (`limiter`) is now imported from `src.ib.ratelimiter`
# to coordinate all historical data requests and stay within IB's limits.


# ── Daily bars (Phase 5B: duration is now a parameter) ────────────────────────

async def fetch_daily_bars(
    ib: IB,
    contract: Contract,
    duration: str = "20 D",
    max_attempts: int = 2,
    timeout: float = 45.0,
) -> Optional[List[BarData]]:
    """Fetch daily OHLC bars for a contract. Returns None on failure.

    duration: IB durationStr (e.g. "20 D" for ATR, "300 D" for EMA-200).
    Retries once with a 3-second backoff to handle IB transient failures.
    timeout: max seconds to wait for IB's response before treating this attempt as
    failed — guards against IB data-farm hangs blocking the whole batch indefinitely.
    """
    sym = contract.symbol
    for attempt in range(1, max_attempts + 1):
        try:
            bars = await asyncio.wait_for(
                ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime="",
                    durationStr=duration,
                    barSizeSetting=_BAR_SIZE,
                    whatToShow="TRADES",
                    useRTH=True,
                    formatDate=1,
                ),
                timeout=timeout,
            )
            if bars:
                log.debug("%s: received %d bars (%s → %s)", sym, len(bars), bars[0].date, bars[-1].date)
                return list(bars)
            log.warning("%s: empty bars on attempt %d/%d", sym, attempt, max_attempts)
        except asyncio.TimeoutError:
            log.warning("%s: reqHistoricalData timed out after %.0fs on attempt %d/%d", sym, timeout, attempt, max_attempts)
        except Exception as e:
            log.warning("%s: reqHistoricalData failed on attempt %d/%d: %s", sym, attempt, max_attempts, e)

        if attempt < max_attempts:
            log.info("%s: retrying historical bars in 3s...", sym)
            await asyncio.sleep(3.0)

    log.error("%s: historical bars unavailable after %d attempt(s) — symbol will be dropped", sym, max_attempts)
    return None


async def fetch_all_daily_bars(
    ib: IB,
    contracts: List[Contract],
    pacing: PacingConfig,
    duration: str = "20 D",
    concurrency: int = 10,
) -> dict[str, List[BarData]]:
    """Fetch daily bars for all contracts concurrently with rate limiting."""
    semaphore = asyncio.Semaphore(concurrency)
    timeout = pacing.historical_request_timeout_seconds

    async def worker(contract: Contract) -> tuple[str, list[BarData]] | None:
        async with semaphore:
            await limiter.acquire(min_gap=pacing.historical_delay_seconds)
            bars = await fetch_daily_bars(ib, contract, duration=duration, timeout=timeout)
            if bars:
                return contract.symbol, bars
        return None

    tasks = [worker(c) for c in contracts]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: dict[str, list[BarData]] = {}
    for i, res in enumerate(task_results):
        if isinstance(res, Exception):
            log.error("%s: daily bars worker failed: %s", contracts[i].symbol, res)
        elif res:
            symbol, bars = res
            results[symbol] = bars

    log.info("Fetched historical bars for %d / %d symbols", len(results), len(contracts))
    return results


# ── Pre-market 1-min bars (Phase 2A) ──────────────────────────────────────────

@dataclass
class PremarketData:
    pre_market_high: Optional[float]
    pre_market_low: Optional[float]
    rvol_pre_market: Optional[float]
    pre_market_volume: Optional[float]   # sum of 1-min TRADES bars 4:00–9:30 AM (SIP composite)


def _bar_date_key(bar) -> str:
    """Return the bar's calendar date as 'YYYYMMDD'.

    ib_async returns bar.date as a datetime.datetime for intraday bar sizes
    (e.g. "1 min") but as a string/date for daily bars — handle both.
    """
    d = bar.date
    if hasattr(d, "strftime"):
        return d.strftime("%Y%m%d")
    return str(d)[:8]


def _bar_time(bar) -> dtime:
    """Return the bar's time-of-day, regardless of whether bar.date is a
    datetime object or a 'YYYYMMDD HH:MM:SS' string."""
    d = bar.date
    if hasattr(d, "time"):
        return d.time()
    time_str = str(d)[9:17]  # "HH:MM:SS" from "YYYYMMDD HH:MM:SS"
    return dtime(*map(int, time_str.split(":")))


def _is_premarket(bar) -> bool:
    """Return True if the bar's time falls in the 04:00–09:29 ET window."""
    return _PM_START <= _bar_time(bar) < _PM_END


async def fetch_premarket_1min_bars(
    ib: IB,
    contract: Contract,
    rvol_lookback_days: int = 5,
    timeout: float = 45.0,
) -> PremarketData:
    """Fetch 1-min pre-market bars to compute high, low, and relative volume."""
    sym = contract.symbol
    empty = PremarketData(None, None, None, None)
    duration = f"{rvol_lookback_days + 2} D"
    prev_raise = ib.RaiseRequestErrors
    ib.RaiseRequestErrors = True
    try:
        bars = await asyncio.wait_for(
            ib.reqHistoricalDataAsync(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting="1 min",
                whatToShow="TRADES",
                useRTH=False,
                formatDate=1,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning("%s: premarket 1-min bars timed out after %.0fs", sym, timeout)
        return empty
    except Exception as e:
        log.warning("%s: premarket 1-min bars failed: %s", sym, e)
        return empty
    finally:
        ib.RaiseRequestErrors = prev_raise

    if not bars:
        log.warning("%s: premarket 1-min bars returned empty — check IB data subscription", sym)
        return empty

    # Group bars by calendar date ("YYYYMMDD")
    by_date: Dict[str, list] = defaultdict(list)
    for b in bars:
        by_date[_bar_date_key(b)].append(b)

    all_dates = sorted(by_date.keys())
    if not all_dates:
        return empty

    today_str   = all_dates[-1]
    prior_dates = all_dates[:-1]

    today_pm  = [b for b in by_date[today_str] if _is_premarket(b)]
    prior_pms = {d: [b for b in by_date[d] if _is_premarket(b)] for d in prior_dates}

    if not today_pm:
        log.debug("%s: no pre-market bars for today", sym)
        return empty

    pre_market_high = max(b.high   for b in today_pm)
    pre_market_low  = min(b.low    for b in today_pm)
    today_pm_vol   = sum(b.volume for b in today_pm)

    # rvol: compare today's cumulative vol to the same clock-minute across prior days
    latest_t = max(_bar_time(b) for b in today_pm)

    def _pm_vol_to(day_bars: list, cutoff: dtime) -> float:
        return sum(
            b.volume for b in day_bars
            if _bar_time(b) <= cutoff
        )

    prior_vols = [
        _pm_vol_to(prior_pms[d], latest_t)
        for d in prior_dates
        if prior_pms.get(d)
    ]
    prior_vols = [v for v in prior_vols if v > 0]

    rvol = (
        round(today_pm_vol / (sum(prior_vols) / len(prior_vols)), 2)
        if prior_vols else None
    )

    return PremarketData(
        pre_market_high=pre_market_high,
        pre_market_low=pre_market_low,
        rvol_pre_market=rvol,
        pre_market_volume=today_pm_vol if today_pm_vol > 0 else None,
    )


async def fetch_all_premarket_bars(
    ib: IB,
    contracts: List[Contract],
    pacing: PacingConfig,
    rvol_lookback_days: int = 5,
    concurrency: int = 3,
) -> Dict[str, PremarketData]:
    """Fetch pre-market 1-min bars for all contracts concurrently."""
    semaphore = asyncio.Semaphore(concurrency)
    timeout = pacing.historical_request_timeout_seconds

    async def worker(contract: Contract) -> tuple[str, PremarketData]:
        async with semaphore:
            await limiter.acquire(min_gap=pacing.historical_delay_seconds)
            data = await fetch_premarket_1min_bars(ib, contract, rvol_lookback_days, timeout=timeout)
            return contract.symbol, data

    tasks = [worker(c) for c in contracts]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: Dict[str, PremarketData] = {}
    for i, res in enumerate(task_results):
        if isinstance(res, Exception):
            log.error("%s: premarket bars worker failed: %s", contracts[i].symbol, res)
        elif res:
            symbol, data = res
            results[symbol] = data

    log.info("Fetched premarket 1-min bars for %d symbols", len(results))
    return results


# ── Previous session VWAP (Phase 3A) ──────────────────────────────────────────

async def fetch_prev_session_vwap(ib: IB, contract: Contract, timeout: float = 45.0) -> Optional[float]:
    """Compute prior RTH session VWAP from 1-min bars."""
    sym = contract.symbol
    prev_raise = ib.RaiseRequestErrors
    ib.RaiseRequestErrors = True
    try:
        bars = await asyncio.wait_for(
            ib.reqHistoricalDataAsync(
                contract,
                endDateTime="",
                durationStr="2 D",
                barSizeSetting="1 min",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning("%s: vwap 1-min bars timed out after %.0fs", sym, timeout)
        return None
    except Exception as e:
        log.warning("%s: vwap 1-min bars failed: %s", sym, e)
        return None
    finally:
        ib.RaiseRequestErrors = prev_raise

    if not bars:
        log.warning("%s: vwap 1-min bars returned empty — check IB data subscription", sym)
        return None

    by_date: Dict[str, list] = defaultdict(list)
    for b in bars:
        by_date[_bar_date_key(b)].append(b)

    all_dates = sorted(by_date.keys())
    if len(all_dates) < 2:
        return None  # need at least today + one prior session

    prior_bars = by_date[all_dates[-2]]
    total_vol = sum(b.volume for b in prior_bars)
    if total_vol == 0:
        return None

    vwap = sum(b.close * b.volume for b in prior_bars) / total_vol
    return round(vwap, 4)


async def fetch_all_prev_session_vwap(
    ib: IB,
    contracts: List[Contract],
    pacing: PacingConfig,
    concurrency: int = 3,
) -> Dict[str, Optional[float]]:
    """Fetch previous-session VWAP for all contracts concurrently."""
    semaphore = asyncio.Semaphore(concurrency)
    timeout = pacing.historical_request_timeout_seconds

    async def worker(contract: Contract) -> tuple[str, float | None]:
        async with semaphore:
            await limiter.acquire(min_gap=pacing.historical_delay_seconds)
            vwap = await fetch_prev_session_vwap(ib, contract, timeout=timeout)
            return contract.symbol, vwap

    tasks = [worker(c) for c in contracts]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: Dict[str, Optional[float]] = {}
    for i, res in enumerate(task_results):
        if isinstance(res, Exception):
            log.error("%s: vwap worker failed: %s", contracts[i].symbol, res)
        elif res:
            symbol, vwap = res
            results[symbol] = vwap

    log.info("Fetched prev-session VWAP for %d symbols", len(results))
    return results
