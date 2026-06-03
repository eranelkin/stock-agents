from __future__ import annotations

from pydantic import BaseModel


class SectorInput(BaseModel):
    """A single sector entry from Sectors.json."""

    name: str
    etf_symbol: str | None = None
