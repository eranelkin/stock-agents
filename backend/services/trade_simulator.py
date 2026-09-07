from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from typing import Any

from backend.services.market_data import Candle

_RANGE_SPLIT = re.compile(r"\s*[-–—]\s*")
_TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}")


@dataclass(frozen=True)
class Recommendation:
    entry_low: float
    entry_high: float
    entry_time_start: time
    entry_time_end: time
    sl_low: float | None
    sl_high: float | None
    tp_low: float | None
    tp_high: float | None


@dataclass(frozen=True)
class SimulationOutcome:
    fill_status: str  # filled | no_fill
    fill_time: Any | None = None
    fill_price: float | None = None
    exit_reason: str | None = None  # take_profit | stop_loss | open_eod
    exit_time: Any | None = None
    exit_price: float | None = None
    pnl_pct: float | None = None
    r_multiple: float | None = None
    # Actual price range observed during the entry-time window, regardless of
    # fill outcome — lets the UI explain *why* a no-fill happened (price never
    # reached the entry zone vs. no candles existed in that window at all).
    entry_window_low: float | None = None
    entry_window_high: float | None = None


def _clean_number(s: str) -> str:
    """Strip currency symbols and thousand separators (e.g. "$5.80" -> "5.80")."""
    return re.sub(r"[^\d.]", "", s)


def _parse_range(value: str) -> tuple[float, float] | None:
    parts = _RANGE_SPLIT.split(value.strip())
    if len(parts) != 2:
        return None
    try:
        low, high = float(_clean_number(parts[0])), float(_clean_number(parts[1]))
    except ValueError:
        return None
    return (low, high) if low <= high else (high, low)


def _parse_time_window(value: str) -> tuple[time, time] | None:
    matches = _TIME_PATTERN.findall(value)
    if len(matches) != 2:
        return None
    try:
        start = time.fromisoformat(matches[0])
        end = time.fromisoformat(matches[1])
    except ValueError:
        return None
    return start, end


def normalize_recommendation(raw: dict[str, Any]) -> Recommendation | None:
    """Extract a canonical Recommendation from a flattened CEO output dict.

    LLM output key naming isn't consistent across providers (spaces vs
    underscores), so each concept is looked up under both variants.
    """
    lower_map = {str(k).strip().lower(): v for k, v in raw.items() if v is not None}

    def _get(*names: str) -> str | None:
        for name in names:
            v = lower_map.get(name)
            if v is not None:
                return str(v)
        return None

    entry_range_str = _get("entry range", "entry_range")
    entry_time_str = _get("entry time", "entry_time")
    sl_range_str = _get("sl range", "sl_range")
    tp_range_str = _get("tp range", "tp_range")

    entry_bounds = _parse_range(entry_range_str) if entry_range_str else None
    entry_window = _parse_time_window(entry_time_str) if entry_time_str else None
    if entry_bounds is None or entry_window is None:
        return None

    sl_bounds = _parse_range(sl_range_str) if sl_range_str else None
    tp_bounds = _parse_range(tp_range_str) if tp_range_str else None

    return Recommendation(
        entry_low=entry_bounds[0],
        entry_high=entry_bounds[1],
        entry_time_start=entry_window[0],
        entry_time_end=entry_window[1],
        sl_low=sl_bounds[0] if sl_bounds else None,
        sl_high=sl_bounds[1] if sl_bounds else None,
        tp_low=tp_bounds[0] if tp_bounds else None,
        tp_high=tp_bounds[1] if tp_bounds else None,
    )


def simulate_trade(rec: Recommendation, candles: list[Candle]) -> SimulationOutcome:
    """Walk 1-minute candles chronologically and simulate the CEO's recommended trade.

    Entry: the first candle within the entry-time window whose range overlaps the
    entry-price range triggers a fill, priced at the entry boundary nearest the
    candle's open (the exact intrabar fill price isn't knowable from OHLC alone).

    Exit: once filled, each subsequent candle is checked for a stop-loss or
    take-profit touch. If a single candle touches both, stop-loss is assumed to
    have happened first (conservative default). If neither is hit by the last
    candle of the day, the position is marked open at the last close.
    """
    if not candles:
        return SimulationOutcome(fill_status="no_fill")

    ordered = sorted(candles, key=lambda c: c.timestamp)

    window_candles = [
        c for c in ordered if rec.entry_time_start <= c.timestamp.time() <= rec.entry_time_end
    ]
    entry_window_low = min((c.low for c in window_candles), default=None)
    entry_window_high = max((c.high for c in window_candles), default=None)

    fill_idx: int | None = None
    for i, c in enumerate(ordered):
        t = c.timestamp.time()
        if rec.entry_time_start <= t <= rec.entry_time_end:
            if c.low <= rec.entry_high and c.high >= rec.entry_low:
                fill_idx = i
                break

    if fill_idx is None:
        return SimulationOutcome(
            fill_status="no_fill",
            entry_window_low=entry_window_low,
            entry_window_high=entry_window_high,
        )

    fill_candle = ordered[fill_idx]
    fill_price = min(max(fill_candle.open, rec.entry_low), rec.entry_high)

    exit_reason: str | None = None
    exit_time = None
    exit_price: float | None = None
    for c in ordered[fill_idx + 1 :]:
        sl_hit = rec.sl_high is not None and c.low <= rec.sl_high
        tp_hit = rec.tp_low is not None and c.high >= rec.tp_low
        if sl_hit:
            exit_reason, exit_price, exit_time = "stop_loss", rec.sl_high, c.timestamp
            break
        if tp_hit:
            exit_reason, exit_price, exit_time = "take_profit", rec.tp_low, c.timestamp
            break

    if exit_reason is None:
        last = ordered[-1]
        exit_reason, exit_price, exit_time = "open_eod", last.close, last.timestamp

    pnl_pct = (exit_price - fill_price) / fill_price * 100
    r_multiple = None
    if rec.sl_high is not None and fill_price != rec.sl_high:
        r_multiple = (exit_price - fill_price) / (fill_price - rec.sl_high)

    return SimulationOutcome(
        fill_status="filled",
        fill_time=fill_candle.timestamp,
        fill_price=fill_price,
        exit_reason=exit_reason,
        exit_time=exit_time,
        exit_price=exit_price,
        pnl_pct=pnl_pct,
        r_multiple=r_multiple,
        entry_window_low=entry_window_low,
        entry_window_high=entry_window_high,
    )
