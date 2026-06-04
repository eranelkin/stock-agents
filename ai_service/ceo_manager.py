from __future__ import annotations

import asyncio
from typing import Any

from ai_service.models.llm_client import LLMClient
from ai_service.models.search_client import SearchClient
from ai_service.pipeline import Pipeline
from ai_service.schemas.input import CeoInput
from ai_service.schemas.run import ModelConfig, PromptConfig
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_output
from ai_service.utils.run_logger import RunLogger

logger = get_logger(__name__)


class CeoManager:
    """Layer 5 — CEO pipeline manager.

    Runs CEO pipelines on a per-ticker streaming basis: as soon as StockAggregator
    completes a ticker (writes stock_{ticker}.yaml), that ticker's CEO pipeline(s)
    start immediately — without waiting for other tickers to finish.

    One Pipeline is spawned per ticker × model_config pair, matching the same
    fan-out pattern as the Layer 2 stocks pipeline.
    """

    def __init__(
        self,
        total_tickers: int,
        model_configs: list[ModelConfig],
        prompts: list[PromptConfig],
        semaphore: asyncio.Semaphore,
        run_dir: str,
        output_format: str,
        run_logger: RunLogger | None = None,
    ) -> None:
        self._total = total_tickers
        self._model_configs = model_configs
        self._prompts = prompts
        self._semaphore = semaphore
        self._run_dir = run_dir
        self._output_format = output_format
        self._run_logger = run_logger
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    async def on_ticker_ready(self, ticker: str, agents: dict[str, Any]) -> None:
        """Called by StockAggregator when a ticker's aggregated data is ready.

        Non-blocking: puts the ticker into the internal queue so CeoManager.run()
        can spawn pipelines immediately.
        """
        await self._queue.put((ticker, agents))
        logger.info("CEO ticker enqueued", extra={"ticker": ticker})

    async def run(self) -> None:
        """Consume the queue and spawn CEO Pipeline tasks as tickers arrive.

        Waits until all expected tickers have been received, then waits for all
        spawned tasks to complete before returning.
        """
        if not self._prompts:
            return

        tasks: list[asyncio.Task[None]] = []
        for _ in range(self._total):
            ticker, agents = await self._queue.get()
            entity = CeoInput(name=ticker, agents=agents)
            for mc in self._model_configs:
                tasks.append(asyncio.create_task(self._run_one(entity, mc)))

        if tasks:
            await asyncio.gather(*tasks)

    async def _run_one(self, entity: CeoInput, mc: ModelConfig) -> None:
        """Run one CEO pipeline for a single ticker × model pair."""
        search_client = SearchClient(run_logger=self._run_logger)
        pipeline = Pipeline(
            entity=entity,
            entity_name=entity.name,
            prompts=self._prompts,
            pipeline_semaphore=self._semaphore,
            llm_client=LLMClient(mc, run_logger=self._run_logger),
            model_name=mc.name,
            search_client=search_client,
            run_logger=self._run_logger,
            pipeline_type="ceo",
            run_dir=self._run_dir,
            output_prefix="CEO_",
        )
        output = await pipeline.run()
        await write_output(
            data=output.model_dump(),
            entity_name=output.ticker,
            output_dir=self._run_dir,
            output_format=self._output_format,
            output_prefix="CEO_",
        )
        logger.info(
            "CEO pipeline output written",
            extra={"ticker": entity.name, "model": mc.name},
        )
