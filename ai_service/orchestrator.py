from __future__ import annotations

import asyncio
import json
import time
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
from ai_service.stock_aggregator import StockAggregator
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_combined_output, write_output
from ai_service.utils.run_logger import RunLogger

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
        self._dt_str: str = ""

    async def run(self) -> None:
        """Entry point: orchestrate the full run lifecycle."""
        logger.info(
            "Orchestrator started",
            extra={"run_id": self.run_id, "model_count": len(self.model_configs)},
        )
        await self._set_status("running")

        run_dir = self._make_run_dir()
        await self._set_output_dir(run_dir)

        log_path = str(Path(settings.output_dir) / "logs" / f"{self._dt_str}.html")
        run_logger = RunLogger(log_path, run_id=self.run_id)
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M:%S UTC")
        await run_logger.open(run_id=self.run_id, started_at=started_at)

        stock_aggregator = StockAggregator(
            expected_pipelines=["stocks"],
            run_dir=run_dir,
            output_format=settings.output_format,
            run_logger=run_logger,
        )

        run_start = time.monotonic()
        try:
            agent_prompts = self.prompts_by_category.get("agents", [])
            sector_prompts = self.prompts_by_category.get("sectors", [])
            await run_logger.run_start(
                mode=settings.agent_mode,
                models=[f"{mc.name} ({mc.model_id})" for mc in self.model_configs],
                tickers=[t.get("name") or t.get("symbol", str(t)) for t in self.tickers],
                agent_prompts=[p.title for p in agent_prompts],
                sector_prompts=[p.title for p in sector_prompts],
            )

            semaphore = asyncio.Semaphore(settings.max_concurrent_pipelines)

            done_events: dict[str, asyncio.Event] = {
                cfg.name: asyncio.Event() for cfg in PIPELINE_REGISTRY
            }

            async def run_pipeline_type(cfg: PipelineTypeConfig) -> None:
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

                models_to_use = (
                    [self.model_configs[0]]
                    if cfg.output_mode == "single_file"
                    else self.model_configs
                )

                search_client = SearchClient(run_logger=run_logger)

                pipelines = [
                    Pipeline(
                        entity=entity,
                        entity_name=entity.name,
                        prompts=type_prompts,
                        pipeline_semaphore=semaphore,
                        llm_client=LLMClient(mc, run_logger=run_logger),
                        model_name=mc.name,
                        search_client=search_client,
                        run_logger=run_logger,
                        pipeline_type=cfg.name,
                        run_dir=run_dir,
                        output_prefix=cfg.output_prefix,
                    )
                    for mc in models_to_use
                    for entity in entities
                ]

                logger.info(
                    f"Pipeline type '{cfg.name}' running {len(pipelines)} pipelines",
                    extra={"run_id": self.run_id},
                )

                async def run_one(p: Pipeline) -> PipelineOutput:
                    output = await p.run()
                    if cfg.output_mode == "per_entity":
                        await write_output(
                            data=output.model_dump(),
                            entity_name=output.ticker,
                            output_dir=run_dir,
                            output_format=settings.output_format,
                            output_prefix=cfg.output_prefix,
                        )
                        if cfg.triggers_aggregation:
                            await stock_aggregator.add_contribution(
                                ticker=output.ticker,
                                pipeline_name=cfg.name,
                                agents=output.agents,
                            )
                    return output

                outputs: list[PipelineOutput] = list(
                    await asyncio.gather(*[run_one(p) for p in pipelines])
                )

                if cfg.output_mode == "single_file":
                    await self._write_outputs(cfg, outputs, run_dir)

                if cfg.persist_to_db:
                    await self._persist_ticker_results(outputs)

                done_events[cfg.name].set()
                logger.info(
                    f"Pipeline type '{cfg.name}' completed",
                    extra={"run_id": self.run_id},
                )

            await asyncio.gather(*[run_pipeline_type(cfg) for cfg in PIPELINE_REGISTRY])

            total_duration_ms = int((time.monotonic() - run_start) * 1000)
            await run_logger.run_end(total_duration_ms=total_duration_ms)
            await self._set_status("completed")
            logger.info("Orchestrator completed", extra={"run_id": self.run_id})

        except asyncio.CancelledError:
            logger.info("Orchestrator cancelled", extra={"run_id": self.run_id})
            await self._set_status("cancelled")
            raise
        except Exception:
            logger.exception("Orchestrator failed", extra={"run_id": self.run_id})
            await self._set_status("failed")
        finally:
            await run_logger.close()

    def _make_run_dir(self) -> str:
        """Create and return a timestamped output subfolder under outputs/runs/."""
        self._dt_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = str(Path(settings.output_dir) / "runs" / self._dt_str)
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
