from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv

load_dotenv()  # must run before litellm is imported so API keys are in os.environ

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai_service.config import settings
from ai_service.orchestrator import Orchestrator
from ai_service.schemas.run import ModelConfig, PromptConfig
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)

# Registry of cancellable asyncio Tasks keyed by run_id.
_active_tasks: dict[str, asyncio.Task[None]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Path(settings.output_dir, "runs").mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir, "logs").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Stock-Agents AI Service", lifespan=lifespan)


class RunRequest(BaseModel):
    run_id: str
    models: list[ModelConfig]
    tickers: list[dict[str, Any]]
    prompts: list[PromptConfig]
    sector_prompts: list[PromptConfig] = []


@app.post("/run", status_code=202)
async def trigger_run(request: RunRequest) -> dict[str, str]:
    """Accept a run request and process it asynchronously as a cancellable task."""
    task = asyncio.create_task(
        _run_orchestrator(
            request.run_id,
            request.models,
            request.tickers,
            request.prompts,
            request.sector_prompts,
        ),
        name=f"run-{request.run_id}",
    )
    _active_tasks[request.run_id] = task
    logger.info(
        "Run accepted",
        extra={"run_id": request.run_id, "models": [m.name for m in request.models]},
    )
    return {"status": "accepted", "run_id": request.run_id}


@app.post("/stop/{run_id}", status_code=200)
async def stop_run(run_id: str) -> dict[str, str]:
    """Cancel an active run task by run_id."""
    task = _active_tasks.get(run_id)
    if task is None or task.done():
        raise HTTPException(status_code=404, detail="No active run found for this ID")
    task.cancel()
    logger.info("Run cancellation requested", extra={"run_id": run_id})
    return {"status": "cancelling", "run_id": run_id}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _run_orchestrator(
    run_id: str,
    model_configs: list[ModelConfig],
    tickers: list[dict[str, Any]],
    prompts: list[PromptConfig],
    sector_prompts: list[PromptConfig],
) -> None:
    try:
        await Orchestrator(
            run_id=run_id,
            model_configs=model_configs,
            tickers=tickers,
            prompts=prompts,
            sector_prompts=sector_prompts,
        ).run()
    finally:
        _active_tasks.pop(run_id, None)
