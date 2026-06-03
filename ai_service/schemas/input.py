from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class TickerInput(BaseModel):
    """A single ticker entry from Data.json. Accepts 'name' or 'symbol' as the identifier key.
    All extra fields (e.g. Market cap, ATR, price) are preserved and passed through to the LLM."""

    model_config = ConfigDict(extra="allow")

    name: str
    sector: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data: object) -> object:
        if isinstance(data, dict) and "name" not in data and "symbol" in data:
            data = {**data, "name": data["symbol"]}
        return data
