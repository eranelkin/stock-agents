from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from dotenv import set_key, unset_key
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AIModel
from backend.db.session import get_session
from backend.schemas.model import ModelActiveUpdate, ModelCreate, ModelResponse, ModelUpdate

router = APIRouter(prefix="/models", tags=["models"])

_ENV_FILE = ".env"


def _build_response(model: AIModel) -> ModelResponse:
    configured = bool(
        model.api_key_env_var and os.environ.get(model.api_key_env_var)
    )
    return ModelResponse(
        id=model.id,
        name=model.name,
        model_id=model.model_id,
        provider=model.provider,
        base_url=model.base_url,
        api_key_configured=configured,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("", response_model=list[ModelResponse])
async def list_models(
    active: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ModelResponse]:
    """List all models, optionally filtered by active state."""
    q = select(AIModel).order_by(AIModel.created_at)
    if active is not None:
        q = q.where(AIModel.is_active == active)
    result = await session.execute(q)
    return [_build_response(m) for m in result.scalars().all()]


@router.post("", response_model=ModelResponse, status_code=201)
async def create_model(
    body: ModelCreate, session: AsyncSession = Depends(get_session)
) -> ModelResponse:
    """Create a model. If api_key is provided, it is written to .env — never stored in DB."""
    model = AIModel(
        name=body.name,
        model_id=body.model_id,
        provider=body.provider,
        base_url=body.base_url,
    )
    session.add(model)
    await session.flush()  # get the id before writing env var

    if body.api_key:
        env_var = f"MODEL_API_KEY_{model.id.hex[:8].upper()}"
        set_key(_ENV_FILE, env_var, body.api_key)
        os.environ[env_var] = body.api_key
        model.api_key_env_var = env_var

    await session.commit()
    await session.refresh(model)
    return _build_response(model)


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: uuid.UUID,
    body: ModelUpdate,
    session: AsyncSession = Depends(get_session),
) -> ModelResponse:
    """Update a model. Provide api_key only to change it; omit to keep existing."""
    model = await session.get(AIModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    if body.name is not None:
        model.name = body.name
    if body.model_id is not None:
        model.model_id = body.model_id
    if body.provider is not None:
        model.provider = body.provider
    if body.base_url is not None:
        model.base_url = body.base_url

    if body.api_key:
        env_var = model.api_key_env_var or f"MODEL_API_KEY_{model.id.hex[:8].upper()}"
        set_key(_ENV_FILE, env_var, body.api_key)
        os.environ[env_var] = body.api_key
        model.api_key_env_var = env_var

    model.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(model)
    return _build_response(model)


@router.patch("/{model_id}/active", response_model=ModelResponse)
async def toggle_active(
    model_id: uuid.UUID,
    body: ModelActiveUpdate,
    session: AsyncSession = Depends(get_session),
) -> ModelResponse:
    """Set the active state of a model."""
    model = await session.get(AIModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    model.is_active = body.is_active
    model.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(model)
    return _build_response(model)


@router.delete("/{model_id}", status_code=204, response_class=Response)
async def delete_model(
    model_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """Delete a model and remove its API key from .env if present."""
    model = await session.get(AIModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    if model.api_key_env_var:
        unset_key(_ENV_FILE, model.api_key_env_var)
        os.environ.pop(model.api_key_env_var, None)

    await session.delete(model)
    await session.commit()
    return Response(status_code=204)
