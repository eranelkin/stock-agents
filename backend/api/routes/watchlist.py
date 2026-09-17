from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from fastapi import APIRouter, HTTPException, Response

from backend.config import settings
from backend.schemas.watchlist import WatchlistEntry, WatchlistEntryCreate, WatchlistEntryUpdate

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _watchlist_path(env: Literal["prod", "test"]) -> Path:
    suffix = "_test" if env == "test" else ""
    base_path = Path(settings.interactive_service_path).resolve()
    return base_path / "config" / f"watchlist{suffix}.yaml"


def _read_entries(path: Path) -> list[WatchlistEntry]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text()) or {}
    entries_raw = raw.get("watchlist") or []
    entries: list[WatchlistEntry] = []
    for item in entries_raw:
        try:
            entries.append(WatchlistEntry(**item))
        except Exception:
            continue
    return entries


def _write_entries(path: Path, entries: list[WatchlistEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"watchlist": [e.model_dump() for e in entries]}
    path.write_text(yaml.safe_dump(data, sort_keys=False))


@router.get("", response_model=list[WatchlistEntry])
async def list_watchlist(env: Literal["prod", "test"] = "prod") -> list[WatchlistEntry]:
    """List all symbols currently in the IBK watchlist for the given environment."""
    return _read_entries(_watchlist_path(env))


@router.post("", response_model=WatchlistEntry, status_code=201)
async def add_watchlist_entry(
    body: WatchlistEntryCreate, env: Literal["prod", "test"] = "prod"
) -> WatchlistEntry:
    """Add a symbol to the watchlist."""
    path = _watchlist_path(env)
    entries = _read_entries(path)
    symbol = body.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    if any(e.symbol == symbol for e in entries):
        raise HTTPException(status_code=409, detail=f"{symbol} is already in the watchlist")
    entry = WatchlistEntry(
        symbol=symbol,
        sec_type=body.sec_type,
        exchange=body.exchange,
        currency=body.currency,
    )
    entries.append(entry)
    _write_entries(path, entries)
    return entry


@router.put("/{symbol}", response_model=WatchlistEntry)
async def update_watchlist_entry(
    symbol: str, body: WatchlistEntryUpdate, env: Literal["prod", "test"] = "prod"
) -> WatchlistEntry:
    """Update a symbol's watchlist entry."""
    path = _watchlist_path(env)
    entries = _read_entries(path)
    symbol = symbol.strip().upper()
    idx = next((i for i, e in enumerate(entries) if e.symbol == symbol), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist")

    current = entries[idx]
    new_symbol = (body.symbol or current.symbol).strip().upper()
    if new_symbol != symbol and any(e.symbol == new_symbol for e in entries):
        raise HTTPException(status_code=409, detail=f"{new_symbol} is already in the watchlist")

    updated = WatchlistEntry(
        symbol=new_symbol,
        sec_type=body.sec_type if body.sec_type is not None else current.sec_type,
        exchange=body.exchange if body.exchange is not None else current.exchange,
        currency=body.currency if body.currency is not None else current.currency,
    )
    entries[idx] = updated
    _write_entries(path, entries)
    return updated


@router.delete("/{symbol}", status_code=204, response_class=Response)
async def delete_watchlist_entry(symbol: str, env: Literal["prod", "test"] = "prod") -> Response:
    """Remove a symbol from the watchlist."""
    path = _watchlist_path(env)
    entries = _read_entries(path)
    symbol = symbol.strip().upper()
    remaining = [e for e in entries if e.symbol != symbol]
    if len(remaining) == len(entries):
        raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist")
    _write_entries(path, remaining)
    return Response(status_code=204)
