from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator


class SectorInput(BaseModel):
    """A single sector entry from Sectors.json. Accepts 'name' or 'symbol' as the identifier key."""

    name: str
    etf_symbol: str | None = None
    quote: dict[str, Any] | None = None
    pre_market: dict[str, Any] | None = None
    sentiment: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data: object) -> object:
        if isinstance(data, dict) and "name" not in data and "symbol" in data:
            data = {**data, "name": data["symbol"]}
        return data
