from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
import yfinance as yf

from ai_service.utils.logger import get_logger

logger = get_logger(__name__)

# Yahoo Finance hard-caps intraday history regardless of the period we request.
# Use these ceilings so we always get the maximum available data.
_INTRADAY_MAX_PERIOD: dict[str, str] = {
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
}


async def fetch_candles(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """Fetch OHLCV candles for a ticker from Yahoo Finance.

    Args:
        symbol: Ticker symbol, e.g. "AAPL".
        interval: yfinance interval string, e.g. "1d", "1h", "30m", "15m", "5m".
        period: History window for non-intraday intervals (e.g. "2y").
                Overridden automatically for intraday intervals by _INTRADAY_MAX_PERIOD.

    Returns:
        DataFrame with Open/High/Low/Close/Volume columns indexed by datetime.
        Returns an empty DataFrame if the symbol is invalid or no data is available.
    """
    resolved_period = _INTRADAY_MAX_PERIOD.get(interval, period)

    def _download() -> pd.DataFrame:
        ticker_obj = yf.Ticker(symbol)
        return ticker_obj.history(
            period=resolved_period,
            interval=interval,
            prepost=False,
            auto_adjust=True,
        )

    try:
        df = await asyncio.to_thread(_download)
    except Exception as exc:
        logger.warning(
            f"yfinance fetch failed for {symbol}: {exc}",
            extra={"ticker": symbol, "interval": interval},
        )
        return pd.DataFrame()

    if df.empty:
        logger.warning(
            f"No candle data returned for {symbol}",
            extra={"ticker": symbol, "interval": interval},
        )
    else:
        logger.debug(
            f"Fetched {len(df)} candles for {symbol}",
            extra={"ticker": symbol, "interval": interval, "candle_count": len(df)},
        )

    return df


async def fetch_info(symbol: str) -> dict[str, Any]:
    """Fetch ticker metadata from Yahoo Finance (marketCap, sector, industry, etc.).

    Returns an empty dict on any failure — callers must treat every field as optional.
    """
    def _get_info() -> dict[str, Any]:
        return yf.Ticker(symbol).info or {}

    try:
        info = await asyncio.to_thread(_get_info)
        logger.debug(f"Fetched info for {symbol}", extra={"ticker": symbol})
        return info
    except Exception as exc:
        logger.warning(
            f"yfinance info fetch failed for {symbol}: {exc}",
            extra={"ticker": symbol},
        )
        return {}
