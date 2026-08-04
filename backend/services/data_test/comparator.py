from __future__ import annotations

import asyncio

from backend.schemas.data_test import DataTestField, DataTestResult
from backend.services.data_test import finnhub_source, fmp_source, interactive_service_source, yahoo_finance_source
from backend.services.data_test.field_registry import load_fields

# Small-phase scope: interactive_service + finnhub are fetched for now. The remaining
# two modules are fully built and already verified against live APIs — re-enabling one
# is just moving its entry from _DISABLED_SOURCES back into _SOURCES.
_SOURCES = {
    "interactive_service": interactive_service_source.fetch,
    "finnhub": finnhub_source.fetch,
}
_DISABLED_SOURCES = {
    "yahoo_finance": yahoo_finance_source.fetch,
    "fmp": fmp_source.fetch,
}
_NOT_ENABLED_MESSAGE = "Not enabled yet — coming in a later phase"


async def run_comparison(symbols: list[str]) -> DataTestResult:
    """Fetch the same fields for `symbols` from every enabled source concurrently.

    Every source is isolated with return_exceptions=True — one source failing
    (IB Gateway down, missing API key, rate limit) never blocks the others.
    """
    fields = load_fields()

    outcomes = await asyncio.gather(
        *(fetch(symbols, fields) for fetch in _SOURCES.values()),
        return_exceptions=True,
    )

    values: dict[str, dict[str, dict[str, float | str | None]]] = {
        symbol: {field["key"]: {} for field in fields} for symbol in symbols
    }
    source_errors: dict[str, str | None] = {name: _NOT_ENABLED_MESSAGE for name in _DISABLED_SOURCES}

    for source_name, outcome in zip(_SOURCES.keys(), outcomes):
        if isinstance(outcome, BaseException):
            source_errors[source_name] = f"unexpected error: {outcome}"
            continue
        source_values, error = outcome
        source_errors[source_name] = error
        for symbol in symbols:
            symbol_values = source_values.get(symbol, {})
            for field in fields:
                values[symbol][field["key"]][source_name] = symbol_values.get(field["key"])

    return DataTestResult(
        fields=[DataTestField(key=f["key"], label=f["label"]) for f in fields],
        symbols=symbols,
        values=values,
        source_errors=source_errors,
    )
