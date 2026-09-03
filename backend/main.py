from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv(override=True)  # load .env before pydantic-settings so MODEL_API_KEY_* vars are in os.environ

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update as sql_update

from backend.api.broadcaster import broadcaster
from backend.api.routes import chat, feargreed, models, prompts, results, runs
from backend.api.routes.screener import router as screener_router
from backend.config import settings
from backend.db.models import Run
from backend.db.session import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # On startup: mark any orphaned pending/running runs as failed.
    # Their backing asyncio tasks were destroyed when the service last stopped,
    # so they will never complete on their own.
    async with AsyncSessionLocal() as session:
        await session.execute(
            sql_update(Run)
            .where(Run.status.in_(["pending", "running"]))
            .values(
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error="Run was orphaned by a service restart and will not complete.",
            )
        )
        await session.commit()

    task = asyncio.create_task(broadcaster.start(AsyncSessionLocal))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Stock-Agents Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(results.router)
app.include_router(models.router)
app.include_router(prompts.router)
app.include_router(chat.router)
app.include_router(feargreed.router)
app.include_router(screener_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
