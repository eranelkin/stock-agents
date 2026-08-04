from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import settings
from backend.services.data_test.field_registry import resolve_path_list

logger = logging.getLogger(__name__)


async def fetch(
    symbols: list[str], fields: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, float | str | None]], str | None]:
    """Fetch Yahoo Finance data by reusing the ai-service /enrich endpoint.

    ai_service.enricher already computes rsi_14, ema_20/50/200, atr_%, market_cap,
    etc. from yfinance via indicators.json (see ai_service/enricher/enricher.py and
    backend/api/routes/runs.py's enrich_preview, which proxies the same endpoint).
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.ai_service_url}/enrich",
                json={"tickers": [{"name": s} for s in symbols], "candle_frequency": "1d"},
                timeout=120.0,
            )
            resp.raise_for_status()
            enriched: list[dict[str, Any]] = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("yahoo_finance_source failed: %s", exc)
        return {}, f"could not reach ai-service: {exc}"

    result: dict[str, dict[str, float | str | None]] = {}
    failed: list[str] = []
    for symbol, record in zip(symbols, enriched):
        if record.get("enrichment_status") == "failed":
            failed.append(symbol)
        values: dict[str, float | str | None] = {}
        for field in fields:
            cfg = field.get("yahoo_finance")
            if not cfg:
                continue
            values[field["key"]] = resolve_path_list(record, cfg["path"])
        result[symbol] = values

    error = f"enrichment failed for: {', '.join(failed)}" if failed else None
    return result, error
