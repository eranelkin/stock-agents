from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_output

if TYPE_CHECKING:
    from ai_service.ceo_manager import CeoManager

logger = get_logger(__name__)


def _flatten_agent_output(agent_output: dict[str, Any]) -> dict[str, Any]:
    """Unwrap stocks[0] if present and drop the symbol field."""
    if isinstance(agent_output, dict):
        stocks_list = agent_output.get("stocks")
        if isinstance(stocks_list, list) and stocks_list:
            flat = dict(stocks_list[0])
            flat.pop("symbol", None)
            return flat
    return agent_output


class StockAggregator:
    """Collects per-pipeline agent contributions for each ticker and writes
    agg_{ticker}.yaml as soon as all expected pipelines have contributed.

    Phase 2: expected_pipelines=["stocks"] — writes immediately on stocks completion.
    Future:  expected_pipelines=["stocks", "sectors", "macro"] — waits for all three.

    When a CEO manager is provided, it is notified immediately after each ticker is
    written so the CEO pipeline for that ticker can start without waiting for others.

    Args:
        expected_pipelines: Pipeline names that must contribute before writing.
        run_dir: Output directory for the current run.
        output_format: "yaml" or "json".
        run_logger: Optional run logger for HTML log output.
        ceo_manager: Optional CeoManager to notify on each ticker completion.
    """

    def __init__(
        self,
        expected_pipelines: list[str],
        run_dir: str,
        output_format: str,
        run_logger: Any | None = None,
        ceo_manager: CeoManager | None = None,
    ) -> None:
        self._expected = set(expected_pipelines)
        self._run_dir = run_dir
        self._output_format = output_format
        self._run_logger = run_logger
        self._ceo_manager = ceo_manager
        self._contributions: dict[str, dict[str, Any]] = defaultdict(dict)
        self._entity_dicts: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def add_contribution(
        self,
        ticker: str,
        pipeline_name: str,
        agents: dict[str, Any],
        entity_dict: dict[str, Any] | None = None,
    ) -> None:
        """Register one pipeline's agent data for a ticker.

        Writes agg_{ticker}.yaml immediately when all expected pipeline
        contributions have been received for this ticker.

        Args:
            ticker: The stock ticker symbol.
            pipeline_name: Name of the contributing pipeline (e.g. "stocks").
            agents: The agents dict from the pipeline's PipelineOutput.
            entity_dict: The raw input entity fields (stored on first call per ticker).
        """
        async with self._lock:
            self._contributions[ticker][pipeline_name] = agents
            if entity_dict and ticker not in self._entity_dicts:
                self._entity_dicts[ticker] = entity_dict
            if self._expected.issubset(self._contributions[ticker].keys()):
                await self._write(ticker)

    async def _write(self, ticker: str) -> None:
        """Build the new agg_{ticker}.yaml structure and write it."""
        contributions = self._contributions[ticker]
        entity_dict = self._entity_dicts.get(ticker, {})

        # Build stock section: input fields + agent outputs from stocks pipeline
        stock: dict[str, Any] = {}
        stock["company_name"] = entity_dict.get("company_name", "")
        for k, v in entity_dict.items():
            if k not in {"name", "company_name"}:
                stock[k] = v
        for agent_title, agent_output in contributions.get("stocks", {}).items():
            key = agent_title.lower().replace(" ", "_")
            stock[key] = _flatten_agent_output(agent_output)

        # Merge all agents for CEO notification
        merged_agents: dict[str, Any] = {}
        for agents_data in contributions.values():
            merged_agents.update(agents_data)

        output: dict[str, Any] = {
            "symbol": ticker,
            "stock": stock,
            "sectors": contributions.get("sectors"),
            "macro": contributions.get("macro"),
        }

        await write_output(
            data=output,
            entity_name=ticker,
            output_dir=self._run_dir,
            output_format=self._output_format,
            output_prefix="agg_",
        )
        logger.info(
            "Stock aggregated output written",
            extra={"ticker": ticker, "source_pipelines": sorted(contributions.keys())},
        )
        if self._ceo_manager:
            await self._ceo_manager.on_ticker_ready(ticker, merged_agents)
