from __future__ import annotations

from pydantic import BaseModel


class WatchlistEntry(BaseModel):
    symbol: str
    sec_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"


class WatchlistEntryCreate(BaseModel):
    symbol: str
    sec_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"


class WatchlistEntryUpdate(BaseModel):
    symbol: str | None = None
    sec_type: str | None = None
    exchange: str | None = None
    currency: str | None = None
