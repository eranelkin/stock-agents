from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator


class MacroInput(BaseModel):
    """A single macro entity from Macro.json. Accepts 'name' or 'symbol' as the identifier key."""

    name: str
    generated_at: str | None = None
    vix: dict[str, Any] | None = None
    spy: dict[str, Any] | None = None
    qqq: dict[str, Any] | None = None
    sectors_summary: list[dict[str, Any]] | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data: object) -> object:
        if isinstance(data, dict) and "name" not in data and "symbol" in data:
            data = {**data, "name": data["symbol"]}
        return data
