from __future__ import annotations

from pydantic import BaseModel, model_validator


class SectorInput(BaseModel):
    """A single sector entry from Sectors.json. Accepts 'name' or 'symbol' as the identifier key."""

    name: str
    etf_symbol: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data: object) -> object:
        if isinstance(data, dict) and "name" not in data and "symbol" in data:
            data = {**data, "name": data["symbol"]}
        return data
