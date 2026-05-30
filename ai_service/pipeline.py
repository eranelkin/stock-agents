from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from ai_service.agent import Agent
from ai_service.aggregator import Aggregator
from ai_service.config import settings
from ai_service.models.llm_client import LLMClient
from ai_service.models.search_client import SearchClient, build_search_query
from ai_service.schemas.input import TickerInput
from ai_service.schemas.output import PipelineOutput
from ai_service.schemas.run import PromptConfig
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


class Pipeline:
    """Processes one ticker through all configured agents and returns aggregated output."""

    def __init__(
        self,
        ticker: TickerInput,
        prompts: list[PromptConfig],
        pipeline_semaphore: asyncio.Semaphore,
        llm_client: LLMClient,
        model_name: str,
        search_client: SearchClient | None = None,
    ) -> None:
        self.ticker = ticker
        self.prompts = prompts
        self.model_name = model_name
        self.pipeline_id = str(uuid.uuid4())
        self._pipeline_semaphore = pipeline_semaphore
        self._agent_semaphore = asyncio.Semaphore(settings.max_concurrent_agents)
        self._llm = llm_client
        self._search = search_client
        self._aggregator = Aggregator()

    async def run(self) -> PipelineOutput:
        """Acquire a pipeline slot, run agents, return the aggregated result."""
        async with self._pipeline_semaphore:
            extra = {
                "ticker": self.ticker.name,
                "pipeline_id": self.pipeline_id,
                "model": self.model_name,
            }
            logger.info("Pipeline started", extra=extra)
            start = time.monotonic()

            if settings.agent_mode == "chain":
                results = await self._run_chain()
            else:
                results = await self._run_parallel()

            duration_ms = int((time.monotonic() - start) * 1000)
            output = self._aggregator.aggregate(
                ticker=self.ticker.name,
                model_name=self.model_name,
                agent_results=results,
                duration_ms=duration_ms,
            )
            logger.info("Pipeline done", extra={**extra, "duration_ms": duration_ms})
            return output

    async def _run_parallel(self) -> dict[str, Any]:
        """Run all searches concurrently, then run all agents concurrently."""
        # Phase 1: fire all searches in parallel for search-enabled prompts
        search_contexts: dict[str, str] = {}
        if self._search and self._search.is_available():
            search_enabled = [p for p in self.prompts if p.search_enabled]
            if search_enabled:
                contexts = await asyncio.gather(
                    *[self._fetch_search(p) for p in search_enabled]
                )
                search_contexts = {p.title: ctx for p, ctx in zip(search_enabled, contexts)}

        # Phase 2: run all agents concurrently with their search contexts
        async def _run_one(prompt_config: PromptConfig) -> tuple[str, dict[str, Any]]:
            async with self._agent_semaphore:
                agent = Agent(
                    agent_id=prompt_config.id,
                    prompt=prompt_config.content,
                    llm_client=self._llm,
                )
                result = await agent.run(
                    ticker_input=self.ticker.model_dump(),
                    ticker=self.ticker.name,
                    pipeline_id=self.pipeline_id,
                    search_context=search_contexts.get(prompt_config.title, ""),
                )
                return prompt_config.title, result

        pairs = await asyncio.gather(*[_run_one(p) for p in self.prompts])
        return dict(pairs)

    async def _run_chain(self) -> dict[str, Any]:
        """Run agents sequentially; each searches and then receives the previous result."""
        results: dict[str, Any] = {}
        previous: dict[str, Any] | None = None

        for prompt_config in self.prompts:
            search_context = ""
            if self._search and self._search.is_available() and prompt_config.search_enabled:
                search_context = await self._fetch_search(prompt_config)

            agent = Agent(
                agent_id=prompt_config.id,
                prompt=prompt_config.content,
                llm_client=self._llm,
            )
            result = await agent.run(
                ticker_input=self.ticker.model_dump(),
                previous_output=previous,
                ticker=self.ticker.name,
                pipeline_id=self.pipeline_id,
                search_context=search_context,
            )
            results[prompt_config.title] = result
            previous = result

        return results

    async def _fetch_search(self, prompt_config: PromptConfig) -> str:
        """Build the query and call Tavily for a single prompt."""
        assert self._search is not None
        query = build_search_query(self.ticker.name, prompt_config.search_query_template)
        return await self._search.search(
            query,
            ticker=self.ticker.name,
            agent_id=prompt_config.id,
        )
