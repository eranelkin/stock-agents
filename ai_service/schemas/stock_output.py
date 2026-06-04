from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StockAggregatedMetadata(BaseModel):
    """Metadata for a stock aggregated output file."""

    aggregated_at: str
    source_pipelines: list[str]


class StockAggregatedOutput(BaseModel):
    """Merged output for one ticker across all contributing pipelines.

    Args:
        ticker: The stock ticker symbol.
        agents: Flat merged dict of all agent results from contributing pipelines.
        metadata: Aggregation metadata including timestamp and source pipeline list.
    """

    ticker: str
    agents: dict[str, Any]
    metadata: StockAggregatedMetadata
