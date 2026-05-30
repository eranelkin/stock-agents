from __future__ import annotations

import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import AIModel, Prompt, Run, TickerResult
from backend.db.session import get_session
from backend.schemas.run import RunCreate, RunResponse

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreate, session: AsyncSession = Depends(get_session)
) -> Run:
    """Create a Run record and trigger the AI service to begin processing."""
    if not body.tickers:
        raise HTTPException(status_code=400, detail="Tickers list is empty.")

    result = await session.execute(
        select(AIModel).where(
            AIModel.id.in_(body.model_ids),
            AIModel.is_active == True,  # noqa: E712
        )
    )
    ai_models = result.scalars().all()

    if not ai_models:
        raise HTTPException(
            status_code=400,
            detail="No active models found for the provided IDs. Enable models in the Models tab first.",
        )

    prompt_result = await session.execute(
        select(Prompt).where(Prompt.category == "agents")
    )
    agent_prompts = prompt_result.scalars().all()
    if not agent_prompts:
        raise HTTPException(
            status_code=400,
            detail="No Agent prompts configured. Add prompts in the Agents tab first.",
        )

    model_configs = [
        {
            "id": str(m.id),
            "name": m.name,
            "model_id": m.model_id,
            "base_url": m.base_url,
            "api_key": os.environ.get(m.api_key_env_var) if m.api_key_env_var else None,
        }
        for m in ai_models
    ]

    run = Run(name=body.name)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.ai_service_url}/run",
                json={
                    "run_id": str(run.id),
                    "models": model_configs,
                    "tickers": body.tickers,
                    "prompts": [
                        {
                            "id": str(p.id),
                            "title": p.title,
                            "content": p.content,
                            "search_enabled": p.search_enabled,
                            "search_query_template": p.search_query_template,
                        }
                        for p in agent_prompts
                    ],
                },
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


@router.delete("/{run_id}", status_code=204, response_class=Response)
async def delete_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """Delete a run and all its ticker results."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await session.execute(sql_delete(TickerResult).where(TickerResult.run_id == run_id))
    await session.delete(run)
    await session.commit()
    return Response(status_code=204)
