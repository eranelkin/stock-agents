from __future__ import annotations

from pydantic import BaseModel


class TickerInput(BaseModel):
    """A single ticker entry from Data.json."""

    name: str
