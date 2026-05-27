from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from ai_service.agent import Agent
from ai_service.aggregator import Aggregator
from ai_service.config import settings
from ai_service.models.llm_client import LLMClient
from ai_service.schemas.input import TickerInput
from ai_service.schemas.output import PipelineOutput
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


class Pipeline:
    """Processes one ticker through all configured agents and returns aggregated output."""

    def __init__(
        self,
        ticker: TickerInput,
        prompts: dict[str, str],
        pipeline_semaphore: asyncio.Semaphore,
    ) -> None:
        self.ticker = ticker
        self.prompts = prompts
        self.pipeline_id = str(uuid.uuid4())
        self._pipeline_semaphore = pipeline_semaphore
        self._agent_semaphore = asyncio.Semaphore(settings.max_concurrent_agents)
        self._llm = LLMClient()
        self._aggregator = Aggregator()

    async def run(self) -> PipelineOutput:
        """Acquire a pipeline slot, run agents, return the aggregated result."""
        async with self._pipeline_semaphore:
            extra = {"ticker": self.ticker.name, "pipeline_id": self.pipeline_id}
            logger.info("Pipeline started", extra=extra)
            start = time.monotonic()

            if settings.agent_mode == "chain":
                results = await self._run_chain()
            else:
                results = await self._run_parallel()

            duration_ms = int((time.monotonic() - start) * 1000)
            output = self._aggregator.aggregate(
                ticker=self.ticker.name,
                agent_results=results,
                duration_ms=duration_ms,
            )
            logger.info("Pipeline done", extra={**extra, "duration_ms": duration_ms})
            return output

    async def _run_parallel(self) -> dict[str, Any]:
        """Run all agents concurrently, bounded by the agent semaphore."""

        async def _run_one(agent_id: str, prompt: str) -> tuple[str, dict[str, Any]]:
            async with self._agent_semaphore:
                agent = Agent(agent_id=agent_id, prompt=prompt, llm_client=self._llm)
                result = await agent.run(
                    ticker_input=self.ticker.model_dump(),
                    ticker=self.ticker.name,
                    pipeline_id=self.pipeline_id,
                )
                return agent_id, result

        pairs = await asyncio.gather(*[_run_one(aid, p) for aid, p in self.prompts.items()])
        return dict(pairs)

    async def _run_chain(self) -> dict[str, Any]:
        """Run agents sequentially, forwarding each result to the next agent."""
        results: dict[str, Any] = {}
        previous: dict[str, Any] | None = None

        for agent_id, prompt in self.prompts.items():
            agent = Agent(agent_id=agent_id, prompt=prompt, llm_client=self._llm)
            result = await agent.run(
                ticker_input=self.ticker.model_dump(),
                previous_output=previous,
                ticker=self.ticker.name,
                pipeline_id=self.pipeline_id,
            )
            results[agent_id] = result
            previous = result

        return results
