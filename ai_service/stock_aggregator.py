from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from ai_service.schemas.stock_output import StockAggregatedMetadata, StockAggregatedOutput
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_output

logger = get_logger(__name__)


class StockAggregator:
    """Collects per-pipeline agent contributions for each ticker and writes
    stock_{ticker}.yaml as soon as all expected pipelines have contributed.

    Phase 2: expected_pipelines=["stocks"] — writes immediately on stocks completion.
    Future:  expected_pipelines=["stocks", "sectors", "macro"] — waits for all three.

    Args:
        expected_pipelines: Pipeline names that must contribute before writing.
        run_dir: Output directory for the current run.
        output_format: "yaml" or "json".
        run_logger: Optional run logger for HTML log output.
    """

    def __init__(
        self,
        expected_pipelines: list[str],
        run_dir: str,
        output_format: str,
        run_logger: Any | None = None,
    ) -> None:
        self._expected = set(expected_pipelines)
        self._run_dir = run_dir
        self._output_format = output_format
        self._run_logger = run_logger
        self._contributions: dict[str, dict[str, Any]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def add_contribution(
        self,
        ticker: str,
        pipeline_name: str,
        agents: dict[str, Any],
    ) -> None:
        """Register one pipeline's agent data for a ticker.

        Writes stock_{ticker}.yaml immediately when all expected pipeline
        contributions have been received for this ticker.

        Args:
            ticker: The stock ticker symbol.
            pipeline_name: Name of the contributing pipeline (e.g. "stocks").
            agents: The agents dict from the pipeline's PipelineOutput.
        """
        async with self._lock:
            self._contributions[ticker][pipeline_name] = agents
            if self._expected.issubset(self._contributions[ticker].keys()):
                await self._write(ticker)

    async def _write(self, ticker: str) -> None:
        """Merge all contributions for a ticker and write stock_{ticker}.yaml."""
        contributions = self._contributions[ticker]
        merged_agents: dict[str, Any] = {}
        for agents_data in contributions.values():
            merged_agents.update(agents_data)

        output = StockAggregatedOutput(
            ticker=ticker,
            agents=merged_agents,
            metadata=StockAggregatedMetadata(
                aggregated_at=datetime.now(timezone.utc).isoformat(),
                source_pipelines=sorted(contributions.keys()),
            ),
        )
        await write_output(
            data=output.model_dump(),
            entity_name=ticker,
            output_dir=self._run_dir,
            output_format=self._output_format,
            output_prefix="stock_",
        )
        logger.info(
            "Stock aggregated output written",
            extra={"ticker": ticker, "source_pipelines": sorted(contributions.keys())},
        )
