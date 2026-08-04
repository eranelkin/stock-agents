from __future__ import annotations

import asyncio
import logging
from typing import List

from ib_async import IB, ScannerSubscription

from src.config.loader import ScannerBatch, ScreenerConfig

log = logging.getLogger(__name__)


async def run_scanner_batches(ib: IB, config: ScreenerConfig) -> List[str]:
    """
    Run one scanner call per batch, deduplicate, and return combined symbol list.

    If scan_batches is empty, falls back to a single scan using the global
    market_cap_min/max_usd fields (backward-compatible with older configs).
    """
    batches = config.scan_batches or [
        ScannerBatch(
            market_cap_min_usd=config.market_cap_min_usd,
            market_cap_max_usd=config.market_cap_max_usd,
        )
    ]

    seen: set[str] = set()
    symbols: List[str] = []

    for i, batch in enumerate(batches):
        if i > 0:
            await asyncio.sleep(3.0)   # pause between scanner calls to allow cleanup
        for sym in await _run_single_scan(ib, config, batch):
            if sym not in seen:
                seen.add(sym)
                symbols.append(sym)

    log.info("Scanner: %d unique symbols from %d batches", len(symbols), len(batches))
    return symbols


async def _run_single_scan(ib: IB, config: ScreenerConfig, batch: ScannerBatch) -> List[str]:
    """
    Execute one IB scanner call with cap range overridden by `batch`.

    IB scanner quirks:
    - marketCapAbove / marketCapBelow / abovePrice / aboveVolume are set directly on
      ScannerSubscription (raw USD / price / shares) — these are real built-in fields
      (confirmed via ib_async's ScannerSubscription dataclass), not paid TagValues.
    - scannerSubscriptionFilterOptions TagValues (e.g. usdMarketCapAbove) require a paid
      data subscription and are disabled on most paper-trading accounts.
    - stockTypeFilter is a built-in ScannerSubscription field (not a TagValue) — works on
      all account types; set to "STOCK" to exclude ETFs/ETNs server-side.
    - Max 50 rows per scan (IB hard limit).
    - Returns contract identifiers only — no price/volume data.
    - ScannerSubscription.aboveVolume filters on *today's cumulative volume so far*,
      not a historical average. That's exactly what pre_market_vol_min wants (today's
      pre-market volume floor), so it's wired to that config field. avg_volume_min
      (a true N-day historical average) has no scanner-side equivalent and is enforced
      client-side instead, against the 20-day average computed from historical bars
      (see filters.reject_reason()).
    """
    sub = ScannerSubscription()
    sub.instrument = config.instrument
    sub.locationCode = config.location_code
    sub.scanCode = config.scan_code
    sub.numberOfRows = min(config.number_of_rows, 50)
    if config.exclude_etfs:
        sub.stockTypeFilter = "STOCK"

    # IMPORTANT: marketCapAbove / marketCapBelow are in MILLIONS of USD (not raw dollars).
    if batch.market_cap_min_usd:
        sub.marketCapAbove = batch.market_cap_min_usd / 1_000_000
    if batch.market_cap_max_usd:
        sub.marketCapBelow = batch.market_cap_max_usd / 1_000_000

    if config.price_min:
        sub.abovePrice = config.price_min
    # aboveVolume intentionally omitted: IB's live volume counter only sees the streaming
    # tick (incomplete, misses off-exchange trades). The client-side filter in filters.py
    # applies pre_market_vol_min after we have the accurate TRADES-bar sum.

    cap_above = f"{batch.market_cap_min_usd / 1_000_000:.0f}M" if batch.market_cap_min_usd else "none"
    cap_below = f"{batch.market_cap_max_usd / 1_000_000:.0f}M" if batch.market_cap_max_usd else "none"
    log.info(
        "Running IB scanner: scanCode=%s, rows=%d, marketCapAbove=%s, marketCapBelow=%s, abovePrice=%s",
        config.scan_code, sub.numberOfRows, cap_above, cap_below,
        config.price_min or "none",
    )

    # Use subscription-based approach instead of reqScannerDataAsync.
    # reqScannerDataAsync waits for IB's scannerDataEnd signal before returning; in some
    # sessions IB never sends scannerDataEnd (keeps the subscription open), causing an
    # indefinite hang.  Instead we subscribe, wait for ib.scannerDataEvent (fired by
    # ib_async when scannerDataEnd arrives), and fall back to a hard timeout so we never
    # block indefinitely.  We always read the list BEFORE cancelling because
    # cancelScannerSubscription → endSubscription removes the dataList from the registry.
    _SCAN_TIMEOUT = 25.0  # seconds to wait for scannerDataEnd before using partial data
    try:
        data_arrived = asyncio.Event()
        scan_data = ib.reqScannerSubscription(sub)

        def _on_scanner_data(dl) -> None:
            if dl.reqId == scan_data.reqId:
                data_arrived.set()

        ib.scannerDataEvent += _on_scanner_data
        try:
            await asyncio.wait_for(data_arrived.wait(), timeout=_SCAN_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(
                "Scanner: scannerDataEnd not received within %.0fs — using partial results",
                _SCAN_TIMEOUT,
            )
        finally:
            ib.scannerDataEvent -= _on_scanner_data

        symbols = [item.contractDetails.contract.symbol for item in scan_data]
        ib.cancelScannerSubscription(scan_data)
    except Exception:
        log.exception("Scanner request failed")
        return []

    if not symbols:
        log.warning(
            "Scanner batch returned 0 symbols — check scan_code/instrument/location_code "
            "or IB Gateway connectivity"
        )
    else:
        log.info("Scanner batch returned %d symbols: %s", len(symbols), symbols)
        if len(symbols) >= sub.numberOfRows:
            log.warning(
                "Scanner batch returned exactly %d symbols (the configured maximum) — "
                "bucket may be saturated; consider splitting this market-cap range into "
                "smaller scan_batches to capture truncated symbols.",
                len(symbols),
            )
    return symbols
