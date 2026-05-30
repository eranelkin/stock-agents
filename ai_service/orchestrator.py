from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from ai_service.config import settings
from ai_service.db import models
from ai_service.db.session import AsyncSessionLocal
from ai_service.models.llm_client import LLMClient
from ai_service.models.search_client import SearchClient
from ai_service.pipeline import Pipeline
from ai_service.schemas.input import TickerInput
from ai_service.schemas.run import ModelConfig, PromptConfig
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_output

logger = get_logger(__name__)


class Orchestrator:
    """Loads prompts, runs all (model × ticker) pipelines, persists results to DB and disk."""

    def __init__(
        self,
        run_id: str,
        model_configs: list[ModelConfig],
        tickers: list[dict[str, Any]],
        prompts: list[PromptConfig],
    ) -> None:
        self.run_id = run_id
        self.model_configs = model_configs
        self.tickers = tickers
        self.prompts = prompts

    async def run(self) -> None:
        """Entry point: orchestrate the full run lifecycle."""
        logger.info(
            "Orchestrator started",
            extra={"run_id": self.run_id, "model_count": len(self.model_configs)},
        )
        await self._set_status("running")

        try:
            ticker_inputs = [TickerInput(**item) for item in self.tickers]
            semaphore = asyncio.Semaphore(settings.max_concurrent_pipelines)
            search_client = SearchClient()

            # One pipeline per (model, ticker) combination
            pipelines = [
                Pipeline(
                    ticker=ticker,
                    prompts=self.prompts,
                    pipeline_semaphore=semaphore,
                    llm_client=LLMClient(mc),
                    model_name=mc.name,
                    search_client=search_client,
                )
                for mc in self.model_configs
                for ticker in ticker_inputs
            ]

            outputs = await asyncio.gather(*[p.run() for p in pipelines])

            async with AsyncSessionLocal() as session:
                for output in outputs:
                    session.add(
                        models.TickerResult(
                            run_id=uuid.UUID(self.run_id),
                            ticker=output.ticker,
                            output=output.model_dump(),
                        )
                    )
                await session.commit()

            for output in outputs:
                await write_output(
                    data=output.model_dump(),
                    ticker=output.ticker,
                    output_dir=settings.output_dir,
                    output_format=settings.output_format,
                )

            await self._set_status("completed")
            logger.info("Orchestrator completed", extra={"run_id": self.run_id})

        except Exception:
            logger.exception("Orchestrator failed", extra={"run_id": self.run_id})
            await self._set_status("failed")

    async def _set_status(self, status: str, error: str | None = None) -> None:
        """Update the Run row status in the database."""
        values: dict[str, Any] = {"status": status}
        if status in ("completed", "failed"):
            values["completed_at"] = datetime.now(timezone.utc)
        if error:
            values["error"] = error
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(models.Run)
                .where(models.Run.id == uuid.UUID(self.run_id))
                .values(**values)
            )
            await session.commit()
