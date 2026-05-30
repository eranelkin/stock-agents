from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from dotenv import load_dotenv

load_dotenv()  # must run before litellm is imported so API keys are in os.environ

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from ai_service.db.models import Base
from ai_service.db.session import engine
from ai_service.orchestrator import Orchestrator
from ai_service.schemas.run import ModelConfig, PromptConfig
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Stock-Agents AI Service", lifespan=lifespan)


class RunRequest(BaseModel):
    run_id: str
    models: list[ModelConfig]
    tickers: list[dict[str, Any]]
    prompts: list[PromptConfig]


@app.post("/run", status_code=202)
async def trigger_run(
    request: RunRequest, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Accept a run request and process it asynchronously in the background."""
    background_tasks.add_task(
        _run_orchestrator, request.run_id, request.models, request.tickers, request.prompts
    )
    logger.info(
        "Run accepted",
        extra={"run_id": request.run_id, "models": [m.name for m in request.models]},
    )
    return {"status": "accepted", "run_id": request.run_id}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _run_orchestrator(
    run_id: str,
    model_configs: list[ModelConfig],
    tickers: list[dict[str, Any]],
    prompts: list[PromptConfig],
) -> None:
    await Orchestrator(
        run_id=run_id, model_configs=model_configs, tickers=tickers, prompts=prompts
    ).run()
