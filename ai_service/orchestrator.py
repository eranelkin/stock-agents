from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiofiles
from sqlalchemy import update

from ai_service.config import settings
from ai_service.db import models
from ai_service.db.session import AsyncSessionLocal
from ai_service.pipeline import Pipeline
from ai_service.schemas.input import TickerInput
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_output
from ai_service.utils.prompt_loader import load_prompts

logger = get_logger(__name__)


class Orchestrator:
    """Loads tickers and prompts, runs all pipelines, persists results to DB and disk."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    async def run(self) -> None:
        """Entry point: orchestrate the full run lifecycle."""
        logger.info("Orchestrator started", extra={"run_id": self.run_id})
        await self._set_status("running")

        try:
            prompts = await load_prompts("Prompts.json")
            tickers = await self._load_tickers("Data.json")

            semaphore = asyncio.Semaphore(settings.max_concurrent_pipelines)
            pipelines = [
                Pipeline(ticker=t, prompts=prompts, pipeline_semaphore=semaphore)
                for t in tickers
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

    async def _load_tickers(self, path: str) -> list[TickerInput]:
        """Read Data.json and return validated TickerInput objects."""
        async with aiofiles.open(path) as f:
            content = await f.read()
        return [TickerInput(**item) for item in json.loads(content)]

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
