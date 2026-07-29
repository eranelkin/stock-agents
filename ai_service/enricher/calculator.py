from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import pandas_ta  # noqa: F401 — registers the .ta DataFrame accessor

from ai_service.utils.logger import get_logger

logger = get_logger(__name__)

# Strips trailing numeric parameter suffixes from pandas-ta column names.
# e.g. MACD_12_26_9 → MACD, BBU_20_2.0 → BBU, STOCHk_14_3_3 → STOCHk
_NUMERIC_SUFFIX = re.compile(r"(_[\d.]+)+$")


def _clean_col(col: str) -> str:
    """Lowercase a pandas-ta column name and strip its numeric parameter suffix."""
    return _NUMERIC_SUFFIX.sub("", str(col)).lower()


def _format_compact_number(value: float | int | None) -> str | float | int | None:
    """Format a large number with a B/M suffix, e.g. 2_160_000_000 -> "2.16B".

    Values under 1,000,000 are returned unchanged (no suffix applied).
    """
    if value is None:
        return None
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return value


def _resolve_raw(df: pd.DataFrame, spec: dict[str, Any]) -> Any:
    """Read a single scalar from the DataFrame by column name and row offset.

    spec keys:
        source  — column name (case-insensitive): Open, High, Low, Close, Volume
        offset  — row index from the end (default -1 = latest candle, -2 = previous)
    """
    source: str = spec["source"]
    offset: int = spec.get("offset", -1)

    col_map = {c.lower(): c for c in df.columns}
    actual_col = col_map.get(source.lower())
    if actual_col is None:
        logger.warning(f"Raw field '{source}' not found in DataFrame columns: {list(df.columns)}")
        return None

    try:
        val = df[actual_col].iloc[offset]
        return None if pd.isna(val) else round(float(val), 4)
    except IndexError:
        logger.warning(
            f"Raw field '{source}' offset {offset} out of range (DataFrame has {len(df)} rows)"
        )
        return None


def _resolve_rolling(df: pd.DataFrame, spec: dict[str, Any]) -> Any:
    """Compute a rolling min or max over the last N trading days.

    spec keys:
        source  — column name (case-insensitive): High, Low, Close, etc.
        stat    — "min", "max", or "mean"
        window  — number of trading days (default 252 = ~1 year)

    The window is converted to candles automatically, so it works correctly
    for both daily and intraday DataFrames.
    """
    source: str = spec["source"]
    stat: str = spec["stat"]
    days: int = spec.get("window", 252)

    col_map = {c.lower(): c for c in df.columns}
    actual_col = col_map.get(source.lower())
    if actual_col is None:
        logger.warning(f"Rolling field '{source}' not found in DataFrame columns: {list(df.columns)}")
        return None

    # Derive candles-per-day from the actual data so this works for any interval.
    unique_days = len(df.index.normalize().unique()) if hasattr(df.index, "normalize") else len(df)
    candles_per_day = max(1, len(df) / max(1, unique_days))
    window_rows = min(int(round(days * candles_per_day)), len(df))

    series = df[actual_col].tail(window_rows)

    if stat == "min":
        val = series.min()
    elif stat == "max":
        val = series.max()
    elif stat == "mean":
        val = series.mean()
    else:
        logger.warning(f"Unknown rolling stat '{stat}' — supported: min, max, mean")
        return None

    return None if pd.isna(val) else round(float(val), 4)


def _resolve_session_vwap(df: pd.DataFrame, spec: dict[str, Any]) -> Any:
    """Calculate the VWAP for a specific completed trading session.

    VWAP resets each day. For intraday data this groups candles by date and returns
    the final cumulative VWAP for the target session (= full-session VWAP).
    For daily data VWAP degenerates to the typical price (H+L+C)/3 of that candle.

    spec keys:
        session_offset — sessions back from most recent (default -1 = previous, 0 = current)
    """
    session_offset: int = spec.get("session_offset", -1)

    try:
        vwap_series = df.ta.vwap()
        if vwap_series is None or vwap_series.empty:
            logger.warning("VWAP calculation returned no data")
            return None

        dates = (
            df.index.normalize()
            if hasattr(df.index, "normalize")
            else pd.DatetimeIndex(df.index).normalize()
        )
        unique_dates = sorted(dates.unique())

        # session_offset=0  → unique_dates[-1]  (current, possibly in-progress)
        # session_offset=-1 → unique_dates[-2]  (previous completed session)
        target_idx = -1 + session_offset
        if abs(target_idx) > len(unique_dates):
            logger.warning(
                f"session_offset={session_offset} out of range — "
                f"only {len(unique_dates)} sessions available"
            )
            return None

        target_date = unique_dates[target_idx]
        session_vwap = vwap_series[dates == target_date]

        if session_vwap.empty:
            return None

        val = session_vwap.iloc[-1]
        return None if pd.isna(val) else round(float(val), 4)

    except Exception as exc:
        logger.warning(f"session_vwap calculation failed: {exc}")
        return None


def _resolve_ema(df: pd.DataFrame, spec: dict[str, Any], timeframe: str | None) -> dict[str, Any]:
    """Compute EMA for multiple lengths and group them into one nested object.

    spec keys:
        lengths — list of EMA periods to compute (e.g. [9, 20, 50, 200])

    Returns {"ema_9": float | None, ..., "timeframe": str | None}.
    """
    lengths: list[int] = spec.get("lengths", [])
    result: dict[str, Any] = {}

    for length in lengths:
        try:
            series = df.ta.ema(length=length)
            val = series.iloc[-1] if series is not None and not series.empty else None
            result[f"ema_{length}"] = None if val is None or pd.isna(val) else round(float(val), 4)
        except Exception as exc:
            logger.warning(f"ema_{length} calculation failed: {exc}")
            result[f"ema_{length}"] = None

    result["timeframe"] = timeframe
    return result


def _resolve_atr(df: pd.DataFrame, spec: dict[str, Any], timeframe: str | None) -> dict[str, Any]:
    """Compute ATR as a percentage of the latest close, grouped with its period and timeframe.

    spec keys:
        period — ATR length (default 14)

    Returns {"value": "X.XX%" | None, "period": int, "timeframe": str | None}.
    """
    period: int = spec.get("period", 14)
    value: str | None = None

    try:
        series = df.ta.atr(length=period)
        val = series.iloc[-1] if series is not None and not series.empty else None
        if val is not None and not pd.isna(val):
            close = float(df["Close"].iloc[-1])
            if close != 0:
                pct = (float(val) / close) * 100
                value = f"{round(pct, 2)}%"
    except Exception as exc:
        logger.warning(f"atr calculation failed: {exc}")

    return {"value": value, "period": period, "timeframe": timeframe}


def _resolve_info(info: dict[str, Any], spec: dict[str, Any]) -> Any:
    """Read a field from the yfinance Ticker.info dict.

    spec keys:
        field — the exact key in the info dict (e.g. "marketCap", "sector", "industry")
    """
    field: str = spec["field"]
    val = info.get(field)
    if val is None:
        return None
    if isinstance(val, float):
        return round(val, 4)
    return val


def _resolve_epoch_date(info: dict[str, Any], spec: dict[str, Any]) -> str | None:
    """Read a unix-timestamp (seconds) field from the yfinance Ticker.info dict and
    format it as an ISO date string, e.g. "2026-07-27".

    spec keys:
        field — the exact key in the info dict (e.g. "earningsTimestamp")
    """
    field: str = spec["field"]
    val = info.get(field)
    if val is None:
        return None
    try:
        return datetime.fromtimestamp(float(val), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError) as exc:
        logger.warning(f"epoch_date field '{field}' has unparseable value {val!r}: {exc}")
        return None


def _resolve_beta(info: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Read beta from the yfinance Ticker.info dict, grouped with a literal timeframe label.

    spec keys:
        timeframe — literal label stamped onto the output as-is (e.g. "1Y monthly")

    Returns {"value": float | None, "timeframe": Any}.
    """
    val = info.get("beta")
    return {
        "value": None if val is None else round(float(val), 4),
        "timeframe": spec.get("timeframe"),
    }


def _resolve_volume_profile(df: pd.DataFrame, spec: dict[str, Any]) -> dict[str, Any] | None:
    """Calculate Volume Profile: POC, VAH, and VAL over a lookback window.

    spec keys:
        window            — lookback in trading days (default 252 = ~1 year)
        num_bins          — price levels to divide the range into (default 100)
        value_area_pct    — % of volume that defines the value area (default 70)
        lookback_sessions — literal value stamped onto the output as-is

    Returns {"poc": float, "vah": float, "val": float, "lookback_sessions": Any} or None on failure.
    """
    days: int = spec.get("window", 252)
    num_bins: int = spec.get("num_bins", 100)
    value_area_pct: float = spec.get("value_area_pct", 70) / 100.0
    lookback_sessions: Any = spec.get("lookback_sessions")

    try:
        # Slice to the lookback window (same day→candle conversion as _resolve_rolling)
        unique_days = len(df.index.normalize().unique()) if hasattr(df.index, "normalize") else len(df)
        candles_per_day = max(1, len(df) / max(1, unique_days))
        window_rows = min(int(round(days * candles_per_day)), len(df))
        dfw = df.tail(window_rows)

        highs   = dfw["High"].to_numpy(dtype=float)
        lows    = dfw["Low"].to_numpy(dtype=float)
        volumes = dfw["Volume"].to_numpy(dtype=float)

        price_min = lows.min()
        price_max = highs.max()
        if price_min == price_max:
            return None

        bin_edges = np.linspace(price_min, price_max, num_bins + 1)
        volume_by_bin = np.zeros(num_bins, dtype=float)

        # Vectorised per-bin overlap for every candle at once
        # bin_lo shape: (num_bins,)   candle shapes: (n_candles,) → broadcast to (num_bins, n_candles)
        bin_lo = bin_edges[:-1, np.newaxis]   # (num_bins, 1)
        bin_hi = bin_edges[1:,  np.newaxis]   # (num_bins, 1)
        c_lo   = lows[np.newaxis, :]          # (1, n_candles)
        c_hi   = highs[np.newaxis, :]         # (1, n_candles)
        c_vol  = volumes[np.newaxis, :]       # (1, n_candles)

        overlap = np.maximum(0.0, np.minimum(c_hi, bin_hi) - np.maximum(c_lo, bin_lo))
        candle_range = np.maximum(c_hi - c_lo, 1e-10)
        # Each bin gets volume * (overlap / candle_range); sum across candles axis
        volume_by_bin = (overlap / candle_range * c_vol).sum(axis=1)

        # POC
        poc_idx = int(np.argmax(volume_by_bin))
        poc = float((bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2)

        # Value area — expand greedily from POC until value_area_pct is covered
        total_volume = volume_by_bin.sum()
        target = total_volume * value_area_pct

        lo_idx = poc_idx - 1
        hi_idx = poc_idx + 1
        va_lo  = poc_idx
        va_hi  = poc_idx
        cumulative = volume_by_bin[poc_idx]

        while cumulative < target:
            can_lo = lo_idx >= 0
            can_hi = hi_idx < num_bins
            if not can_lo and not can_hi:
                break
            vol_lo = volume_by_bin[lo_idx] if can_lo else -1.0
            vol_hi = volume_by_bin[hi_idx] if can_hi else -1.0
            if vol_hi >= vol_lo:
                cumulative += vol_hi
                va_hi = hi_idx
                hi_idx += 1
            else:
                cumulative += vol_lo
                va_lo = lo_idx
                lo_idx -= 1

        vah = float(bin_edges[va_hi + 1])
        val = float(bin_edges[va_lo])

        return {
            "poc": round(poc, 4),
            "vah": round(vah, 4),
            "val": round(val, 4),
            "lookback_sessions": lookback_sessions,
        }

    except Exception as exc:
        logger.warning(f"volume_profile calculation failed: {exc}")
        return None


def _maybe_normalize(
    value: float | None, df: pd.DataFrame, spec: dict[str, Any]
) -> float | None:
    """If spec has "normalize_by", return (value / column_latest) * 100.

    Used to express indicators as a percentage of price (e.g. ATR%).
    """
    normalize_by: str | None = spec.get("normalize_by")
    if normalize_by is None or value is None:
        return value

    col_map = {c.lower(): c for c in df.columns}
    actual_col = col_map.get(normalize_by.lower())
    if actual_col is None:
        logger.warning(f"normalize_by column '{normalize_by}' not found — skipping normalisation")
        return value

    divisor = float(df[actual_col].iloc[-1])
    if divisor == 0:
        return None

    return round((value / divisor) * 100, 4)


def calculate_indicators(
    df: pd.DataFrame,
    indicators: list[dict[str, Any]],
    info: dict[str, Any] | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """Calculate all entries defined in indicators.json.

    Supported entry types (set via the optional "type" field):

    - "indicator" (default): calls the named pandas-ta function.
      Single-value → scalar (supports "normalize_by" for % of price).
      Multi-output (MACD, BBANDS, STOCH) → nested dict with cleaned column names.

    - "raw": reads a column value at a row offset from the OHLCV DataFrame.
      Keys: source (column name), offset (row from end, default -1).

    - "rolling": min, max, or mean of a column over the last N trading days.
      Keys: source, stat ("min"/"max"/"mean"), window (days, default 252).

    - "session_vwap": VWAP for a specific session.
      Keys: session_offset (default -1 = previous session, 0 = current).

    - "info": reads a field from yfinance Ticker.info (marketCap, sector, etc.).
      Keys: field (exact key name in the info dict).

    - "ema": multiple EMA lengths grouped into one nested object, tagged with
      the candle timeframe. Keys: lengths (list of periods).

    - "atr": Average True Range as a percentage of the latest close, grouped
      into one nested object with its period and the candle timeframe.
      Keys: period (default 14).

    - "beta": reads "beta" from yfinance Ticker.info, grouped with a literal
      timeframe label. Keys: timeframe (e.g. "1Y monthly").

    - "epoch_date": reads a unix-timestamp field from yfinance Ticker.info and
      formats it as an ISO date string. Keys: field (e.g. "earningsTimestamp").

    Any entry (except "ema"/"atr", which are already formatted) may also set
    "format": "compact" to render large numeric results with a B/M suffix
    (e.g. 2_160_000_000 -> "2.16B") via _format_compact_number.

    Args:
        df: OHLCV DataFrame (columns Open/High/Low/Close/Volume, datetime index).
        indicators: List of spec dicts loaded from indicators.json.
        info: Optional yfinance Ticker.info dict for "info" type entries.
        timeframe: Candle interval string (e.g. "1d"), stamped onto "ema"/"atr" output.

    Returns:
        Flat dict of {output_key: value}. Failed or missing entries are silently skipped.
    """
    info = info or {}
    result: dict[str, Any] = {}

    for spec in indicators:
        output_key: str = spec["output_key"]
        entry_type: str = spec.get("type", "indicator")

        try:
            if entry_type == "raw":
                result[output_key] = _resolve_raw(df, spec)

            elif entry_type == "rolling":
                result[output_key] = _resolve_rolling(df, spec)

            elif entry_type == "session_vwap":
                result[output_key] = _resolve_session_vwap(df, spec)

            elif entry_type == "volume_profile":
                result[output_key] = _resolve_volume_profile(df, spec)

            elif entry_type == "info":
                result[output_key] = _resolve_info(info, spec)

            elif entry_type == "ema":
                result[output_key] = _resolve_ema(df, spec, timeframe)

            elif entry_type == "atr":
                result[output_key] = _resolve_atr(df, spec, timeframe)

            elif entry_type == "beta":
                result[output_key] = _resolve_beta(info, spec)

            elif entry_type == "epoch_date":
                result[output_key] = _resolve_epoch_date(info, spec)

            else:  # "indicator" (default)
                name: str = spec["name"]
                params: dict[str, Any] = spec.get("params", {})

                fn = getattr(df.ta, name, None)
                if fn is None:
                    logger.warning(f"pandas-ta has no indicator named '{name}' — skipping")
                    continue

                out = fn(**params)
                if out is None:
                    continue

                if isinstance(out, pd.Series):
                    val = out.iloc[-1]
                    scalar = None if pd.isna(val) else round(float(val), 4)
                    result[output_key] = _maybe_normalize(scalar, df, spec)

                elif isinstance(out, pd.DataFrame):
                    if out.empty:
                        continue
                    row = out.iloc[-1]
                    result[output_key] = {
                        _clean_col(col): (None if pd.isna(v) else round(float(v), 4))
                        for col, v in row.items()
                    }

            if spec.get("format") == "compact" and isinstance(result.get(output_key), (int, float)):
                result[output_key] = _format_compact_number(result[output_key])

        except Exception as exc:
            logger.warning(f"Entry '{output_key}' (type={entry_type}) failed: {exc}")

    return result
