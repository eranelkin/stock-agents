from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"
_MAX_CONCURRENT = 5  # stay well under Finnhub's free-tier 60 req/min limit


async def _get(client: httpx.AsyncClient, sem: asyncio.Semaphore, path: str, params: dict) -> dict:
    async with sem:
        resp = await client.get(
            f"{_BASE_URL}{path}", params={**params, "token": settings.finnhub_api_key}, timeout=15.0
        )
        resp.raise_for_status()
        return resp.json()


async def fetch(
    symbols: list[str], fields: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, float | str | None]], str | None]:
    """Fetch price quote, basic-financials metrics, and technical indicators from Finnhub.

    - /quote and /stock/metric are on Finnhub's free tier.
    - /indicator (technical indicators, e.g. RSI/ATR/EMA) has not been verified against a
      live free-tier key here — if it's gated, those cells surface as errors rather than
      breaking the rest of the comparison.
    """
    if not settings.finnhub_api_key:
        return {}, "FINNHUB_API_KEY not configured"

    sem = asyncio.Semaphore(_MAX_CONCURRENT)
    indicator_fields = [f for f in fields if (f.get("finnhub") or {}).get("indicator")]

    async def fetch_symbol(client: httpx.AsyncClient, symbol: str) -> tuple[str, dict, list[str]]:
        errors: list[str] = []
        quote: dict[str, Any] = {}
        metric: dict[str, Any] = {}
        indicators: dict[tuple[str, int], Any] = {}

        # Finnhub can return HTTP 200 with a JSON `null`/unexpected shape body (e.g. an
        # endpoint gated on the current plan) — guard every response, not just transport
        # errors, so one odd response never crashes the whole comparison.
        try:
            quote = (await _get(client, sem, "/quote", {"symbol": symbol})) or {}
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{symbol} quote: {exc}")

        try:
            data = (await _get(client, sem, "/stock/metric", {"symbol": symbol, "metric": "all"})) or {}
            metric = data.get("metric") or {}
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{symbol} metric: {exc}")

        async def fetch_indicator(field: dict) -> None:
            cfg = field["finnhub"]
            key = (cfg["indicator"], cfg["timeperiod"])
            try:
                data = (
                    await _get(
                        client,
                        sem,
                        "/indicator",
                        {
                            "symbol": symbol,
                            "resolution": "D",
                            "indicator": cfg["indicator"],
                            "timeperiod": cfg["timeperiod"],
                        },
                    )
                ) or {}
                series = data.get(cfg["indicator"]) or []
                indicators[key] = series[-1] if series else None
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{symbol} {cfg['indicator']}({cfg['timeperiod']}): {exc}")
                indicators[key] = None

        await asyncio.gather(*(fetch_indicator(f) for f in indicator_fields))

        values: dict[str, float | str | None] = {}
        for field in fields:
            cfg = field.get("finnhub")
            if not cfg:
                continue
            if "quote_field" in cfg:
                values[field["key"]] = quote.get(cfg["quote_field"])
            elif "metric_field" in cfg:
                values[field["key"]] = metric.get(cfg["metric_field"])
            elif "indicator" in cfg:
                values[field["key"]] = indicators.get((cfg["indicator"], cfg["timeperiod"]))
        return symbol, values, errors

    async with httpx.AsyncClient() as client:
        outcomes = await asyncio.gather(
            *(fetch_symbol(client, s) for s in symbols), return_exceptions=True
        )

    all_errors: list[str] = []
    values_by_symbol: dict[str, dict[str, float | str | None]] = {}
    for symbol, outcome in zip(symbols, outcomes):
        if isinstance(outcome, BaseException):
            values_by_symbol[symbol] = {}
            all_errors.append(f"{symbol}: unexpected error: {outcome}")
            continue
        _, values, errors = outcome
        values_by_symbol[symbol] = values
        all_errors.extend(errors)

    error = "; ".join(all_errors) if all_errors else None
    return values_by_symbol, error
