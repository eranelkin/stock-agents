from __future__ import annotations

import json
import os
import uuid
from typing import Any, AsyncGenerator

import litellm
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AIModel
from backend.db.session import get_session

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatAttachment(BaseModel):
    name: str
    content: str
    mime_type: str = "text/plain"


class ChatRequest(BaseModel):
    model_id: str
    messages: list[ChatMessage]
    attachments: list[ChatAttachment] = []


async def _sse_stream(
    model: AIModel,
    messages: list[dict[str, Any]],
    attachments: list[ChatAttachment],
) -> AsyncGenerator[str, None]:
    llm_messages: list[dict[str, Any]] = []
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and attachments and i == len(messages) - 1:
            parts = [msg["content"]]
            for att in attachments:
                parts.append(f"\n\n--- {att.name} ---\n{att.content}")
            llm_messages.append({"role": "user", "content": "".join(parts)})
        else:
            llm_messages.append(msg)

    kwargs: dict[str, Any] = {
        "model": model.model_id,
        "messages": llm_messages,
        "stream": True,
    }
    if model.base_url:
        kwargs["base_url"] = model.base_url
    if model.api_key_env_var:
        key = os.environ.get(model.api_key_env_var)
        if key:
            kwargs["api_key"] = key

    try:
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {json.dumps({'content': delta})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream a chat completion from the selected model via SSE."""
    try:
        model_uuid = uuid.UUID(body.model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model_id")

    model = await session.get(AIModel, model_uuid)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    if not model.is_active:
        raise HTTPException(status_code=400, detail="Model is not active")

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    return StreamingResponse(
        _sse_stream(model, messages, body.attachments),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
