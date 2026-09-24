from __future__ import annotations

"""Fetch IB's stock-loan / cost-to-borrow bulk file.

IB does not expose borrow fee rate through reqMktData/ib_async's streaming tick
data (unlike shortable shares / shortability, which come through the same
market-data subscription the screener already uses) — it is only published as a
periodically-updated flat file covering all US shortable names.

IMPORTANT — verify before relying on this in production:
The exact URL/format below (IBKR's public "usa.txt" short-availability feed) is
the commonly-referenced endpoint for this data, but has not been verified against
a live IBKR account as part of this change. Confirm the URL and column layout
against IBKR's current documentation (Interactive Brokers > Short Stock (SLB)
Availability) before depending on this in production; the parser below is
written defensively (header-driven column lookup, not fixed positions) so a
format drift degrades to "no data" rather than silently misreading columns.
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Default source for IB's short-stock-availability file. Override via
# BORROW_FEE_SOURCE_URL in .env if this endpoint changes.
DEFAULT_BORROW_FEE_URL = "https://www.interactivebrokers.com/ib_hkust/download/usa.txt"

# Column-name aliases the parser will look for in the file's header row
# (case-insensitive), since exact header naming varies across IBKR feed
# revisions.
_SYMBOL_COLS = {"sym", "symbol"}
_FEE_COLS = {"feerate", "fee_rate", "fee"}


def fetch_borrow_fees(url: str = DEFAULT_BORROW_FEE_URL, timeout: float = 15.0) -> dict[str, dict[str, Any]]:
    """Download and parse IB's borrow-fee-rate file into {symbol: {"rate": float}}.

    Returns an empty dict (with a warning logged) on any failure — this is
    best-effort enrichment, never a reason to fail the whole "Get Market Data" run.
    """
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Borrow-fee fetch failed (%s) — skipping borrow_fees this run", exc)
        return {}

    return _parse_borrow_fee_text(resp.text)


def _parse_borrow_fee_text(text: str) -> dict[str, dict[str, Any]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}

    # Find the header row: the first line containing a recognized symbol-column alias.
    header_idx = None
    delimiter = "\t"
    header_fields: list[str] = []
    for i, line in enumerate(lines[:5]):
        for delim in ("\t", "|", ","):
            fields = [f.strip().lower() for f in line.split(delim)]
            if _SYMBOL_COLS & set(fields):
                header_idx, delimiter, header_fields = i, delim, fields
                break
        if header_idx is not None:
            break

    if header_idx is None:
        logger.warning("Borrow-fee file: could not locate a recognizable header row — skipping")
        return {}

    try:
        sym_idx = next(i for i, f in enumerate(header_fields) if f in _SYMBOL_COLS)
        fee_idx = next(i for i, f in enumerate(header_fields) if f in _FEE_COLS)
    except StopIteration:
        logger.warning(
            "Borrow-fee file: header found but missing a recognized fee-rate column "
            "(looked for %s) — skipping", _FEE_COLS,
        )
        return {}

    result: dict[str, dict[str, Any]] = {}
    for line in lines[header_idx + 1:]:
        fields = [f.strip() for f in line.split(delimiter)]
        if len(fields) <= max(sym_idx, fee_idx):
            continue
        symbol = fields[sym_idx].upper()
        if not symbol or symbol.startswith("#"):
            continue
        try:
            rate = float(fields[fee_idx])
        except ValueError:
            continue
        result[symbol] = {"rate": rate}

    logger.info("Borrow-fee file parsed: %d symbols", len(result))
    return result
