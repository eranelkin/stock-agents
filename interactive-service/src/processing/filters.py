from __future__ import annotations

import logging
from typing import List

from src.config.loader import ScreenerConfig
from src.processing.enrichment import StockRecord

log = logging.getLogger(__name__)


def apply_screener_filters(records: List[StockRecord], config: ScreenerConfig) -> List[StockRecord]:
    """
    Apply client-side filters to records after IB data has been fetched.

    Symbols with missing (None) values for a filtered field are treated as
    failing that filter and are excluded.
    """
    kept: List[StockRecord] = []
    for rec in records:
        reason = reject_reason(rec, config)
        if reason:
            log.info("Filtered out %s: %s", rec.symbol, reason)
        else:
            kept.append(rec)

    log.info("Screener filters: %d → %d records", len(records), len(kept))
    return kept


def reject_reason(rec: StockRecord, cfg: ScreenerConfig) -> str:
    if cfg.atr_min is not None:
        if rec.atr is None:
            return f"ATR unavailable (min required: {cfg.atr_min}%)"
        if rec.atr < cfg.atr_min:
            return f"ATR {rec.atr:.2f}% < min {cfg.atr_min}%"

    if cfg.price_min is not None:
        # Use pre-market price as fallback when prev-close tick hasn't arrived
        effective_price = rec.price if rec.price is not None else rec.pre_market_price
        if effective_price is None:
            # Both unavailable — ATR filter already passed so it's unlikely a penny stock
            log.warning("%s: price data unavailable, skipping price_min check", rec.symbol)
        elif effective_price < cfg.price_min:
            return f"price {effective_price:.2f} < min {cfg.price_min}"

    if cfg.pre_market_vol_min is not None:
        vol = rec.pre_market_volume
        if vol is not None and vol < cfg.pre_market_vol_min:
            return f"pre_market_volume {vol:.0f} < min {cfg.pre_market_vol_min:.0f}"

    if cfg.avg_volume_min is not None:
        avg_vol = rec.avg_daily_volume_20d
        if avg_vol is None:
            return f"avg_daily_volume unavailable (min required: {cfg.avg_volume_min:.0f})"
        if avg_vol < cfg.avg_volume_min:
            return f"avg_daily_volume {avg_vol:.0f} < min {cfg.avg_volume_min:.0f}"

    return ""


def filter_symbols_by_avg_volume(
    symbols: List[str],
    bars_map: dict,
    avg_volume_min: float | None,
) -> List[str]:
    """
    Pre-filter on 20-day average daily volume, computed directly from historical bars,
    before the more expensive market-data/premarket/VWAP/volume-profile stages run.

    Mirrors the avg_daily_volume_20d calc in enrichment.py so the early pre-filter and
    the final build_records() figure never disagree.
    """
    if avg_volume_min is None:
        return symbols

    passed = []
    for sym in symbols:
        bars = bars_map.get(sym)
        if not bars:
            log.warning("Drop %s: no historical bars — cannot compute avg_daily_volume", sym)
            continue
        recent = bars[-20:]
        avg_vol = sum(b.volume for b in recent) / len(recent)
        if avg_vol < avg_volume_min:
            log.info("Drop %s: avg_daily_volume=%.0f < min %.0f", sym, avg_vol, avg_volume_min)
        else:
            passed.append(sym)

    log.info("avg_volume_min pre-filter: %d → %d symbols", len(symbols), len(passed))
    return passed


def filter_symbols_by_atr(
    symbols: List[str],
    atr_map: dict[str, float | None],
    atr_min: float | None,
    bars_map: dict | None = None,
) -> List[str]:
    """
    Quick pre-filter on ATR percentage values before fetching market data snapshots.
    Saves API calls for symbols that won't pass the ATR threshold.
    ATR values are expressed as percentages.

    bars_map is optional but recommended — when provided it distinguishes between
    "historical fetch failed" (data issue) and "ATR below threshold" (expected filter).
    """
    if atr_min is None:
        return symbols

    passed = []
    for sym in symbols:
        atr = atr_map.get(sym)
        if atr is None:
            if bars_map is not None and sym not in bars_map:
                log.warning("Drop %s: historical bars fetch failed — ATR cannot be computed", sym)
            else:
                log.warning("Drop %s: insufficient bars for ATR calculation (need ≥15 trading days)", sym)
        elif atr < atr_min:
            log.info("Drop %s: ATR=%.2f%% < min %.2f%%", sym, atr, atr_min)
        else:
            passed.append(sym)

    log.info("ATR pre-filter: %d → %d symbols", len(symbols), len(passed))
    return passed
