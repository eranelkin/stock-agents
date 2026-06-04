from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()  # load .env before pydantic-settings so MODEL_API_KEY_* vars are in os.environ

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.broadcaster import broadcaster
from backend.api.routes import chat, models, prompts, results, runs
from backend.config import settings
from backend.db.session import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
