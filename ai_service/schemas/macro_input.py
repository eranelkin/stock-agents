from __future__ import annotations

from pydantic import BaseModel, model_validator


class MacroInput(BaseModel):
    """A single macro entity from Macro.json. Accepts 'name' or 'symbol' as the identifier key."""

    name: str

    @model_validator(mode="before")
    @classmethod
    def resolve_name(cls, data: object) -> object:
        if isinstance(data, dict) and "name" not in data and "symbol" in data:
            data = {**data, "name": data["symbol"]}
        return data
