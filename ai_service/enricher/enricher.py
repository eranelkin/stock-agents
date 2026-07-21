from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from ai_service.enricher.calculator import calculate_indicators
from ai_service.enricher.fetcher import fetch_candles, fetch_info
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


class Enricher:
    """Fetches market candles and calculates technical indicators for a list of tickers.

    Runs concurrently (bounded by a semaphore) and never raises — failed tickers
    fall back to their original data with enrichment_status="failed".
    """

    def __init__(
        self, indicators_path: str, period: str, max_concurrent: int
    ) -> None:
        """
        Args:
            indicators_path: Path to indicators.json.
            period: yfinance history window for non-intraday intervals (e.g. "2y").
            max_concurrent: Max simultaneous Yahoo Finance fetches.
        """
        self._period = period
        self._semaphore = asyncio.Semaphore(max_concurrent)
        with open(indicators_path) as f:
            config = json.load(f)
        self._indicators: list[dict[str, Any]] = config["indicators"]

    async def enrich(self, ticker_dict: dict[str, Any], frequency: str) -> dict[str, Any]:
        """Enrich one ticker dict with candle data and technical indicators.

        Args:
            ticker_dict: Original ticker object (must contain "name" or "symbol").
            frequency: yfinance interval string, e.g. "1d", "1h", "30m".

        Returns:
            Original ticker dict merged with indicator values and enrichment metadata.
            On any failure, returns the original dict with enrichment_status="failed".
        """
        symbol: str = ticker_dict.get("name") or ticker_dict.get("symbol", "")

        async with self._semaphore:
            try:
                df, info = await asyncio.gather(
                    fetch_candles(symbol, interval=frequency, period=self._period),
                    fetch_info(symbol),
                )

                if df.empty:
                    raise ValueError("No market data returned from Yahoo Finance")

                indicators = calculate_indicators(df, self._indicators, info=info)
                latest_close = float(df["Close"].iloc[-1])

                enriched: dict[str, Any] = {
                    **ticker_dict,
                    "current_price": round(latest_close, 4),
                    "candle_frequency": frequency,
                    "candle_count": len(df),
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "enrichment_status": "ok",
                    **indicators,
                }
                logger.info(
                    f"Enriched {symbol}: {len(df)} candles, {len(indicators)} indicators",
                    extra={"ticker": symbol, "candle_count": len(df), "frequency": frequency},
                )
                return enriched

            except Exception as exc:
                logger.warning(
                    f"Enrichment failed for {symbol}: {exc}",
                    extra={"ticker": symbol},
                )
                return {**ticker_dict, "enrichment_status": "failed"}

    async def enrich_all(
        self, tickers: list[dict[str, Any]], frequency: str
    ) -> list[dict[str, Any]]:
        """Enrich all tickers concurrently, preserving input order.

        Args:
            tickers: List of ticker dicts from the run request.
            frequency: yfinance interval string.

        Returns:
            List of enriched ticker dicts in the same order as input.
        """
        return list(
            await asyncio.gather(*[self.enrich(t, frequency) for t in tickers])
        )
