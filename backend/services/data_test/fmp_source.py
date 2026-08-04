from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://financialmodelingprep.com/api/v3"
_MAX_CONCURRENT = 5


async def _get(client: httpx.AsyncClient, sem: asyncio.Semaphore, path: str, params: dict) -> Any:
    async with sem:
        resp = await client.get(
            f"{_BASE_URL}{path}", params={**params, "apikey": settings.fmp_api_key}, timeout=15.0
        )
        resp.raise_for_status()
        return resp.json()


async def fetch(
    symbols: list[str], fields: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, float | str | None]], str | None]:
    """Fetch quote, profile (for beta), and technical-indicator data from FMP.

    /quote and /profile are on FMP's free tier. /technical_indicator has not been
    verified against a live free-tier key here — if it's gated, those cells surface
    as errors rather than breaking the rest of the comparison.
    """
    if not settings.fmp_api_key:
        return {}, "FMP_API_KEY not configured"

    sem = asyncio.Semaphore(_MAX_CONCURRENT)
    indicator_fields = [f for f in fields if (f.get("fmp") or {}).get("technical_indicator")]

    async def fetch_symbol(client: httpx.AsyncClient, symbol: str) -> tuple[str, dict, list[str]]:
        errors: list[str] = []
        quote: dict[str, Any] = {}
        profile: dict[str, Any] = {}
        indicators: dict[tuple[str, int], Any] = {}

        # FMP can return HTTP 200 with an unexpected JSON shape (e.g. an endpoint gated
        # on the current plan) — guard every response, not just transport errors, so one
        # odd response never crashes the whole comparison.
        try:
            data = await _get(client, sem, f"/quote/{symbol}", {})
            quote = data[0] if data else {}
        except (httpx.HTTPError, ValueError, IndexError, TypeError, KeyError) as exc:
            errors.append(f"{symbol} quote: {exc}")

        try:
            data = await _get(client, sem, f"/profile/{symbol}", {})
            profile = data[0] if data else {}
        except (httpx.HTTPError, ValueError, IndexError, TypeError, KeyError) as exc:
            errors.append(f"{symbol} profile: {exc}")

        async def fetch_indicator(field: dict) -> None:
            cfg = field["fmp"]
            key = (cfg["technical_indicator"], cfg["period"])
            try:
                data = await _get(
                    client,
                    sem,
                    f"/technical_indicator/1day/{symbol}",
                    {"type": cfg["technical_indicator"], "period": cfg["period"]},
                )
                latest = data[0] if data else {}
                indicators[key] = latest.get(cfg["technical_indicator"])
            except (httpx.HTTPError, ValueError, IndexError, TypeError, KeyError) as exc:
                errors.append(f"{symbol} {cfg['technical_indicator']}({cfg['period']}): {exc}")
                indicators[key] = None

        await asyncio.gather(*(fetch_indicator(f) for f in indicator_fields))

        values: dict[str, float | str | None] = {}
        for field in fields:
            cfg = field.get("fmp")
            if not cfg:
                continue
            if "quote_field" in cfg:
                values[field["key"]] = quote.get(cfg["quote_field"])
            elif "profile_field" in cfg:
                values[field["key"]] = profile.get(cfg["profile_field"])
            elif "technical_indicator" in cfg:
                values[field["key"]] = indicators.get((cfg["technical_indicator"], cfg["period"]))
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
