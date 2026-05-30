from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from urllib.parse import urlparse

import litellm
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from tavily import AsyncTavilyClient

from backend.config import settings
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


async def _fetch_search_context(query: str) -> str:
    """Run a Tavily search and return a formatted context block, or empty string on failure."""
    if not settings.search_enabled or not settings.tavily_api_key:
        return ""
    try:
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        raw: dict[str, Any] = await client.search(
            query=query,
            search_depth=settings.search_depth,
            max_results=settings.search_max_results,
        )
        results = raw.get("results", [])
        if not results:
            return ""

        retrieved_at = datetime.now(timezone.utc).isoformat()
        lines = [
            "--- LIVE WEB SEARCH CONTEXT ---",
            f'Query: "{query}"',
            f"Retrieved: {retrieved_at}",
            "",
        ]
        for i, r in enumerate(results, start=1):
            domain = urlparse(r.get("url", "")).netloc or r.get("url", "")
            snippet = r.get("content", "")[:400].rstrip()
            if len(r.get("content", "")) > 400:
                snippet += "..."
            lines += [f"[{i}] {r.get('title', '')}", f"    Source: {domain}", f"    {snippet}", ""]
        lines.append("--- END SEARCH CONTEXT ---")
        return "\n".join(lines)
    except Exception:
        return ""


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

    # Inject live search context based on the last user message
    last_user = next(
        (m["content"] for m in reversed(llm_messages) if m["role"] == "user"), ""
    )
    search_context = await _fetch_search_context(last_user)
    if search_context:
        # Prepend as a system message so any model sees it regardless of tool-calling support
        llm_messages.insert(0, {"role": "system", "content": search_context})

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
