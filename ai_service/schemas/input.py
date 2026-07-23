from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class CeoInput(BaseModel):
    """Input entity for the CEO pipeline (Layer 5).

    Carries the merged agent outputs from all contributing pipelines for one ticker,
    as produced by the StockAggregator.
    """

    symbol: str
    agents: dict[str, Any]


class TickerInput(BaseModel):
    """A single ticker entry from Data.json. Accepts 'symbol' or 'name' as the identifier key.
    All extra fields (e.g. Market cap, ATR, price) are preserved and passed through to the LLM."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    sector: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_symbol(cls, data: object) -> object:
        if isinstance(data, dict) and "symbol" not in data and "name" in data:
            data = {**data, "symbol": data["name"]}
        return data
