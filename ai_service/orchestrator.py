from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import update

from ai_service.config import settings
from ai_service.db import models
from ai_service.db.session import AsyncSessionLocal
from ai_service.models.llm_client import LLMClient
from ai_service.models.search_client import SearchClient
from ai_service.pipeline import Pipeline
from ai_service.pipeline_registry import PIPELINE_REGISTRY, PipelineTypeConfig
from ai_service.schemas.output import PipelineOutput
from ai_service.schemas.run import ModelConfig, PromptConfig
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_combined_output, write_output

logger = get_logger(__name__)


class Orchestrator:
    """Runs all registered pipeline types concurrently, respecting dependency ordering."""

    def __init__(
        self,
        run_id: str,
        model_configs: list[ModelConfig],
        tickers: list[dict[str, Any]],
        prompts: list[PromptConfig],
        sector_prompts: list[PromptConfig],
    ) -> None:
        self.run_id = run_id
        self.model_configs = model_configs
        self.tickers = tickers
        self.prompts_by_category: dict[str, list[PromptConfig]] = {
            "agents": prompts,
            "sectors": sector_prompts,
        }

    async def run(self) -> None:
        """Entry point: orchestrate the full run lifecycle."""
        logger.info(
            "Orchestrator started",
            extra={"run_id": self.run_id, "model_count": len(self.model_configs)},
        )
        await self._set_status("running")

        try:
            run_dir = self._make_run_dir()
            await self._set_output_dir(run_dir)
            semaphore = asyncio.Semaphore(settings.max_concurrent_pipelines)
            search_client = SearchClient()

            # One asyncio.Event per pipeline type for dependency signalling
            done_events: dict[str, asyncio.Event] = {
                cfg.name: asyncio.Event() for cfg in PIPELINE_REGISTRY
            }

            async def run_pipeline_type(cfg: PipelineTypeConfig) -> None:
                # Wait for all declared dependencies to finish first
                for dep in cfg.dependencies:
                    await done_events[dep].wait()

                type_prompts = self.prompts_by_category.get(cfg.prompt_category, [])

                if not type_prompts:
                    if not cfg.required:
                        logger.info(
                            f"Skipping '{cfg.name}' pipeline — no prompts configured",
                            extra={"run_id": self.run_id},
                        )
                        done_events[cfg.name].set()
                        return
                    raise ValueError(
                        f"Required pipeline '{cfg.name}' has no prompts configured"
                    )

                # Load entities: from request (stocks) or from JSON file (others)
                if cfg.use_request_entities:
                    entities = [cfg.entity_schema(**item) for item in self.tickers]
                else:
                    entities = await self._load_entities(
                        getattr(settings, cfg.data_source_key), cfg.entity_schema
                    )

                if not entities:
                    logger.warning(
                        f"No entities found for '{cfg.name}' pipeline",
                        extra={"run_id": self.run_id},
                    )
                    done_events[cfg.name].set()
                    return

                # For single_file output, run with only the first model to keep
                # the combined file unambiguous. Per-entity pipelines use all models.
                models_to_use = (
                    [self.model_configs[0]]
                    if cfg.output_mode == "single_file"
                    else self.model_configs
                )

                pipelines = [
                    Pipeline(
                        entity=entity,
                        entity_name=entity.name,
                        prompts=type_prompts,
                        pipeline_semaphore=semaphore,
                        llm_client=LLMClient(mc),
                        model_name=mc.name,
                        search_client=search_client,
                    )
                    for mc in models_to_use
                    for entity in entities
                ]

                logger.info(
                    f"Pipeline type '{cfg.name}' running {len(pipelines)} pipelines",
                    extra={"run_id": self.run_id},
                )
                outputs: list[PipelineOutput] = list(
                    await asyncio.gather(*[p.run() for p in pipelines])
                )

                await self._write_outputs(cfg, outputs, run_dir)

                if cfg.persist_to_db:
                    await self._persist_ticker_results(outputs)

                done_events[cfg.name].set()
                logger.info(
                    f"Pipeline type '{cfg.name}' completed",
                    extra={"run_id": self.run_id},
                )

            # Launch all pipeline types concurrently; dependency ordering is handled
            # internally via done_events.wait()
            await asyncio.gather(*[run_pipeline_type(cfg) for cfg in PIPELINE_REGISTRY])

            await self._set_status("completed")
            logger.info("Orchestrator completed", extra={"run_id": self.run_id})

        except Exception:
            logger.exception("Orchestrator failed", extra={"run_id": self.run_id})
            await self._set_status("failed")

    def _make_run_dir(self) -> str:
        """Create and return a timestamped output subfolder for this run."""
        dt_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = str(Path(settings.output_dir) / dt_str)
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        return run_dir

    async def _load_entities(self, data_path: str, schema: type) -> list[Any]:
        """Load and validate a list of entities from a JSON file."""
        try:
            async with aiofiles.open(data_path) as f:
                content = await f.read()
            return [schema(**item) for item in json.loads(content)]
        except FileNotFoundError:
            logger.error(f"Data file not found: {data_path}", extra={"run_id": self.run_id})
            return []

    async def _write_outputs(
        self, cfg: PipelineTypeConfig, outputs: list[PipelineOutput], run_dir: str
    ) -> None:
        """Write pipeline outputs to disk based on the pipeline's output_mode."""
        if cfg.output_mode == "per_entity":
            await asyncio.gather(*[
                write_output(
                    data=output.model_dump(),
                    entity_name=output.ticker,
                    output_dir=run_dir,
                    output_format=settings.output_format,
                    output_prefix=cfg.output_prefix,
                )
                for output in outputs
            ])
        else:
            # single_file: combine all entity outputs under their name as the key
            combined = {
                out.ticker: {
                    "agents": out.agents,
                    "metadata": out.metadata.model_dump(),
                }
                for out in outputs
            }
            await write_combined_output(
                data=combined,
                filename=cfg.single_file_name,
                output_dir=run_dir,
                output_format=settings.output_format,
            )

    async def _persist_ticker_results(self, outputs: list[PipelineOutput]) -> None:
        """Persist stock pipeline outputs to the TickerResult table."""
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

    async def _set_output_dir(self, output_dir: str) -> None:
        """Persist the run's output directory path to the database."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(models.Run)
                .where(models.Run.id == uuid.UUID(self.run_id))
                .values(output_dir=output_dir)
            )
            await session.commit()
