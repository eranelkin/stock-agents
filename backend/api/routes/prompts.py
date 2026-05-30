from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Prompt
from backend.db.session import get_session
from backend.schemas.prompt import PromptCreate, PromptResponse, PromptUpdate

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptResponse])
async def list_prompts(
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PromptResponse]:
    """List all prompts, optionally filtered by category."""
    q = select(Prompt).order_by(Prompt.created_at)
    if category is not None:
        q = q.where(Prompt.category == category)
    result = await session.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=PromptResponse, status_code=201)
async def create_prompt(
    body: PromptCreate, session: AsyncSession = Depends(get_session)
) -> Prompt:
    """Create a new prompt."""
    prompt = Prompt(title=body.title, content=body.content, category=body.category)
    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return prompt


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptUpdate,
    session: AsyncSession = Depends(get_session),
) -> Prompt:
    """Update a prompt."""
    prompt = await session.get(Prompt, prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if body.title is not None:
        prompt.title = body.title
    if body.content is not None:
        prompt.content = body.content
    if body.category is not None:
        prompt.category = body.category

    prompt.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}", status_code=204, response_class=Response)
async def delete_prompt(
    prompt_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """Delete a prompt."""
    prompt = await session.get(Prompt, prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await session.delete(prompt)
    await session.commit()
    return Response(status_code=204)
