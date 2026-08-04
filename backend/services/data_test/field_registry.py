from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "data_test_fields.json"


@lru_cache(maxsize=1)
def load_fields() -> list[dict[str, Any]]:
    """Load the Data Test field registry (backend/data_test_fields.json).

    Each entry has a "key"/"label" plus a per-source config (or null if that
    source doesn't support the field): "interactive_service", "yahoo_finance",
    "finnhub", "fmp".
    """
    return json.loads(_REGISTRY_PATH.read_text())["fields"]


_SUFFIXES = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def parse_ibk_scalar(raw: Any) -> float | str | None:
    """Parse an interactive-service formatted output value back to a number.

    interactive-service formats numbers for display (e.g. "3.50T", "50.5M",
    "+2.50%") and uses "Not available from source (...)" / "Not calculated
    (...)" placeholders for missing data. Non-numeric strings (company names,
    etc.) are returned unchanged.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.startswith("Not available") or s.startswith("Not calculated") or s in ("N/A", ""):
        return None

    negative = s.startswith("-")
    body = s.lstrip("+-")
    suffix = body[-1].upper() if body and body[-1].upper() in _SUFFIXES else None
    if suffix:
        body = body[:-1]
    body = body.rstrip("%")

    try:
        value = float(body)
    except ValueError:
        return raw  # not numeric — pass through as-is

    if suffix:
        value *= _SUFFIXES[suffix]
    return -value if negative else value


def get_path(data: Any, path: str) -> Any:
    """Resolve a dotted path (e.g. "ema.ema_20") against a nested dict."""
    current = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def resolve_path_list(data: dict[str, Any], paths: list[str]) -> Any:
    """Return the first non-None value found by trying each dotted path in order."""
    for path in paths:
        value = get_path(data, path)
        if value is not None:
            return value
    return None


def resolve_ibk_path_list(data: dict[str, Any], paths: list[str]) -> float | str | None:
    """Like resolve_path_list, but parses each candidate before checking it's usable.

    interactive-service uses "Not available from source (...)" placeholder strings for
    missing data — those are non-None but must not block falling through to the next
    candidate path (e.g. ["pre_market_price", "prev_close"] outside market hours).
    """
    for path in paths:
        parsed = parse_ibk_scalar(get_path(data, path))
        if parsed is not None:
            return parsed
    return None
