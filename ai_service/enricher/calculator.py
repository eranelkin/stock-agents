from __future__ import annotations

import re
from typing import Any

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
        stat    — "min" or "max"
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
    else:
        logger.warning(f"Unknown rolling stat '{stat}' — supported: min, max")
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
) -> dict[str, Any]:
    """Calculate all entries defined in indicators.json.

    Supported entry types (set via the optional "type" field):

    - "indicator" (default): calls the named pandas-ta function.
      Single-value → scalar (supports "normalize_by" for % of price).
      Multi-output (MACD, BBANDS, STOCH) → nested dict with cleaned column names.

    - "raw": reads a column value at a row offset from the OHLCV DataFrame.
      Keys: source (column name), offset (row from end, default -1).

    - "rolling": min or max of a column over the last N trading days.
      Keys: source, stat ("min"/"max"), window (days, default 252).

    - "session_vwap": VWAP for a specific session.
      Keys: session_offset (default -1 = previous session, 0 = current).

    - "info": reads a field from yfinance Ticker.info (marketCap, sector, etc.).
      Keys: field (exact key name in the info dict).

    Args:
        df: OHLCV DataFrame (columns Open/High/Low/Close/Volume, datetime index).
        indicators: List of spec dicts loaded from indicators.json.
        info: Optional yfinance Ticker.info dict for "info" type entries.

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

            elif entry_type == "info":
                result[output_key] = _resolve_info(info, spec)

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

        except Exception as exc:
            logger.warning(f"Entry '{output_key}' (type={entry_type}) failed: {exc}")

    return result
