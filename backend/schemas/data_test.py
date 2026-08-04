from __future__ import annotations

from pydantic import BaseModel


class DataTestRequest(BaseModel):
    symbols: list[str]


class DataTestField(BaseModel):
    key: str
    label: str


SOURCE_NAMES = ("interactive_service", "yahoo_finance", "finnhub", "fmp")

# {symbol: {field_key: {source_name: value | None}}}
DataTestValues = dict[str, dict[str, dict[str, float | str | None]]]


class DataTestResult(BaseModel):
    fields: list[DataTestField]
    symbols: list[str]
    values: DataTestValues
    source_errors: dict[str, str | None]
