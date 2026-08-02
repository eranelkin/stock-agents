from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from ib_async import IB, Contract

from src.config.loader import PacingConfig

log = logging.getLogger(__name__)

# Tick types requested:
#   233 = RTVolume (real-time volume, last price, last size)
#   236 = Shortable shares
#   258 = Fundamental Ratios (market cap, PE, etc.)
_GENERIC_TICKS = "165,233,236,258"

# Seconds to wait after opening subscriptions before reading ticks.
# Using snapshot=False (streaming) so IB pushes all ticks continuously;
# 10 s is enough for close, bid/ask, volume, and fundamentalRatios to arrive.
_STREAM_WAIT = 10.0


@dataclass
class MarketSnapshot:
    symbol: str
    pre_market_price: Optional[float]    # ticker.last during pre-market
    prev_close: Optional[float]          # regular-session close
    pre_market_volume: Optional[float]   # volume traded in pre-market session
    market_cap_usd: Optional[float]      # fundamentalRatios.MKTCAP × 1M (tick 258)
    pre_market_chg_pct: Optional[float]  # computed: (last - close) / close * 100
    fifty_two_week_high: Optional[float] # TickType HIGH_52_WEEKS (tick 20, genericTick=165)
    fifty_two_week_low: Optional[float]  # TickType LOW_52_WEEKS  (tick 19, genericTick=165)
    shares_outstanding: Optional[float]  # fundamentalRatios.TTMSHOUT × 1M (tick 258)
    beta: Optional[float]                # fundamentalRatios.BETA (tick 258)


def _safe(val: float) -> Optional[float]:
    """Return None if val is nan/None, otherwise the value."""
    if val is None:
        return None
    try:
        return None if math.isnan(val) else val
    except TypeError:
        return None


def _calc_chg_pct(price: Optional[float], close: Optional[float]) -> Optional[float]:
    if price is None or close is None or close == 0:
        return None
    return (price - close) / close * 100


async def fetch_market_snapshots(
    ib: IB,
    contracts: List[Contract],
    pacing: PacingConfig,
) -> Dict[str, MarketSnapshot]:
    """
    Fetch pre-market market data for a batch of contracts.

    Uses snapshot=False (streaming) so IB pushes all tick types continuously.
    snapshot=True often misses tick type 9 (prev close) and tick 258
    (fundamentalRatios) in pre-market conditions. We open subscriptions for
    all contracts, wait for ticks to arrive, read, then cancel everything.

    Processes in batches of max_concurrent_mkt_data to respect IB's hard limit.
    """
    if not contracts:
        return {}

    results: Dict[str, MarketSnapshot] = {}

    # Use delayed streaming (type 3) so ticks arrive even without a live subscription.
    # ib_async maps delayed tick types 66/67/68/74 to the same ticker.bid/ask/last/volume
    # fields as their live counterparts, so _extract_snapshot needs no changes.
    # For accounts with live subscriptions IB will still deliver live data.
    ib.reqMarketDataType(3)

    for batch_num, batch_start in enumerate(range(0, len(contracts), pacing.max_concurrent_mkt_data), 1):
        batch = contracts[batch_start: batch_start + pacing.max_concurrent_mkt_data]
        log.info("Market data batch %d: fetching %d symbols...", batch_num, len(batch))

        # Phase 1: open streaming subscriptions for the whole batch (non-blocking)
        tickers = {}
        for contract in batch:
            ticker = ib.reqMktData(
                contract,
                genericTickList=_GENERIC_TICKS,
                snapshot=False,          # streaming → pushes close, bid/ask, volume reliably
                regulatorySnapshot=False,
            )
            tickers[contract.symbol] = (ticker, contract)
            await asyncio.sleep(pacing.market_data_delay_seconds)

        # Phase 2: wait for all ticks to arrive
        log.debug("Waiting %ss for market data ticks (batch %d of %d)...", _STREAM_WAIT, batch_num, 
                  (len(contracts) + pacing.max_concurrent_mkt_data - 1) // pacing.max_concurrent_mkt_data)
        await asyncio.sleep(_STREAM_WAIT)

        # Phase 3: read and immediately cancel every subscription
        batch_results = 0
        for symbol, (ticker, contract) in tickers.items():
            snapshot = _extract_snapshot(symbol, ticker)
            results[symbol] = snapshot
            ib.cancelMktData(contract)
            
            # Log only if we got meaningful data
            if snapshot.pre_market_price is not None or snapshot.prev_close is not None:
                batch_results += 1
                log.debug(
                    "%s: last=%.2f  close=%.2f  vol=%s  mktcap=%s  chg=%s%%",
                    symbol,
                    snapshot.pre_market_price or 0.0,
                    snapshot.prev_close or 0.0,
                    f"{snapshot.pre_market_volume:.0f}" if snapshot.pre_market_volume is not None else "n/a",
                    f"{snapshot.market_cap_usd / 1e9:.2f}B" if snapshot.market_cap_usd else "n/a",
                    f"{snapshot.pre_market_chg_pct:.2f}" if snapshot.pre_market_chg_pct is not None else "n/a",
                )
            else:
                log.warning("%s: no market data received (price and close both None)", symbol)
        
        log.info("Batch %d: got data for %d / %d symbols", batch_num, batch_results, len(tickers))

        # Wait for all cancellations to process before moving to next batch
        # IB needs time to fully release market data subscriptions and clean up resources
        # Increased from 2s to 3s to ensure reliable cleanup
        if batch_num < (len(contracts) + pacing.max_concurrent_mkt_data - 1) // pacing.max_concurrent_mkt_data:
            log.debug("Waiting 3s for market data subscription cancellations to process...")
            await asyncio.sleep(3.0)

    ib.reqMarketDataType(1)  # restore default (live) for any subsequent IB calls
    log.info("Fetched market snapshots for %d / %d symbols", len(results), len(contracts))
    return results


def _extract_snapshot(symbol: str, ticker) -> MarketSnapshot:
    last = _safe(ticker.last)
    close = _safe(ticker.close)

    # Fallback: if last is unavailable, use bid/ask midpoint
    if last is None:
        bid = _safe(ticker.bid)
        ask = _safe(ticker.ask)
        if bid is not None and ask is not None:
            last = (bid + ask) / 2
            log.debug("%s: using bid/ask midpoint as pre-market price (last was nan)", symbol)

    # Heuristic to fix cases where IB returns day's change in the 'last' field
    # instead of the price. This results in change % values < -100%, which is
    # impossible for a stock price.
    pre_market_price = last
    if last is not None and close is not None and close > 0:
        chg_pct_check = (last - close) / close * 100
        if chg_pct_check <= -100.0:
            log.warning(
                "%s: Detected potential data error from IB: initial change is %.2f%%. "
                "Assuming 'last' field (%.4f) contains daily change, not price.",
                symbol, chg_pct_check, last
            )
            # Correct the values: price is close + change
            pre_market_price = close + last
            log.info(
                "%s: Corrected price to %.2f (close=%.2f, change=%.4f)",
                symbol, pre_market_price, close, last
            )

    market_cap: Optional[float] = None

    # IB delivers fundamentalRatios via tickString tickType 47, which ib_async parses
    # into ticker.fundamentalRatios as a FundamentalRatios DynamicObject.
    # MKTCAP is reported in millions of USD — multiply by 1_000_000 to get raw USD.
    fr = getattr(ticker, "fundamentalRatios", None)
    if fr is not None:
        mktcap_millions = getattr(fr, "MKTCAP", None)
        if mktcap_millions is not None:
            try:
                val = float(mktcap_millions)
                if not math.isnan(val) and val > 0:
                    market_cap = val * 1_000_000
            except (TypeError, ValueError):
                pass

    # shares_outstanding and beta — also delivered via genericTick=258 fundamentalRatios
    shares_outstanding: Optional[float] = None
    beta: Optional[float] = None
    if fr is not None:
        # Shares outstanding must be > 0
        raw_so = getattr(fr, "TTMSHOUT", None)
        if raw_so is not None:
            try:
                val_so = float(raw_so)
                if not math.isnan(val_so) and val_so > 0:
                    shares_outstanding = val_so * 1_000_000
            except (TypeError, ValueError):
                pass
        
        # Beta can be any non-nan float
        raw_beta = getattr(fr, "BETA", None)
        if raw_beta is not None:
            try:
                val_beta = float(raw_beta)
                if not math.isnan(val_beta):
                    beta = val_beta
            except (TypeError, ValueError):
                pass

    if market_cap is None:
        log.debug("%s: market cap not available (fundamentalRatios.MKTCAP missing or not yet received)", symbol)
        # Fallback to calculating from shares outstanding and price
        if shares_outstanding is not None and close is not None and close > 0:
            market_cap = shares_outstanding * close
            log.info(
                "%s: Market cap not in fundamentalRatios. Calculated as "
                "shares_outstanding * prev_close (%.0f * %.2f = %.2fB)",
                symbol, shares_outstanding, close, market_cap / 1e9
            )

    # 52-week high/low — delivered via genericTick=165 (Misc Stats)
    fifty_two_week_high = _safe(getattr(ticker, "high52week", None))
    fifty_two_week_low  = _safe(getattr(ticker, "low52week",  None))

    volume = _safe(ticker.volume)

    return MarketSnapshot(
        symbol=symbol,
        pre_market_price=pre_market_price,
        prev_close=close,
        pre_market_volume=volume,
        market_cap_usd=market_cap,
        pre_market_chg_pct=_calc_chg_pct(pre_market_price, close),
        fifty_two_week_high=fifty_two_week_high,
        fifty_two_week_low=fifty_two_week_low,
        shares_outstanding=shares_outstanding,
        beta=beta,
    )
