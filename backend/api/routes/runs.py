from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import Run
from backend.db.session import get_session
from backend.schemas.run import RunResponse

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(session: AsyncSession = Depends(get_session)) -> Run:
    """Create a Run record and trigger the AI service to begin processing."""
    run = Run()
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.ai_service_url}/run",
                json={"run_id": str(run.id)},
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            run.status = "failed"
            run.error = f"Could not reach ai-service: {exc}"
            await session.commit()
            raise HTTPException(status_code=502, detail="Failed to reach ai-service") from exc

    return run


@router.get("", response_model=list[RunResponse])
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[Run]:
    """Return all runs ordered by creation time descending."""
    result = await session.execute(select(Run).order_by(Run.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Run:
    """Return a single run by ID."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
