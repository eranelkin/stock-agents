from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.data_test import DataTestField, DataTestRequest, DataTestResult
from backend.services.data_test.comparator import run_comparison
from backend.services.data_test.field_registry import load_fields

router = APIRouter(prefix="/data-test", tags=["data-test"])


@router.get("/fields", response_model=list[DataTestField])
async def get_fields() -> list[DataTestField]:
    """Return the comparison field registry so the frontend doesn't hardcode row labels."""
    return [DataTestField(key=f["key"], label=f["label"]) for f in load_fields()]


@router.post("/run", response_model=DataTestResult)
async def run_data_test(body: DataTestRequest) -> DataTestResult:
    """Fetch the same fields for the given symbols from interactive-service, Yahoo
    Finance, Finnhub, and FMP, and return them side by side for comparison."""
    seen: set[str] = set()
    symbols: list[str] = []
    for s in body.symbols:
        sym = s.strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    if not symbols:
        raise HTTPException(status_code=400, detail="Symbols list is empty.")
    return await run_comparison(symbols)
