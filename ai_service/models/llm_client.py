from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from ai_service.config import settings
from ai_service.schemas.run import ModelConfig
from ai_service.utils.logger import get_logger
from ai_service.utils.run_logger import RunLogger

logger = get_logger(__name__)


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class LLMClient:
    """Provider-agnostic async LLM client backed by litellm.acompletion."""

    def __init__(self, model_config: ModelConfig, run_logger: RunLogger | None = None) -> None:
        self._model = model_config.model_id
        self._base_url = model_config.base_url
        self._api_key = model_config.api_key
        self._run_logger = run_logger

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        log_context: dict[str, Any] | None = None,
    ) -> str:
        """Send a chat completion and return the response text."""
        ctx = log_context or {}
        agent_id = ctx.get("agent_id", "")
        prompt_title = ctx.get("prompt_title", "")
        pipeline_id = ctx.get("pipeline_id", "")
        pipeline_type = ctx.get("pipeline_type", "")
        entity = ctx.get("entity", "")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        if self._run_logger:
            await self._run_logger.llm_request(
                agent_id=agent_id,
                prompt_title=prompt_title,
                model=self._model,
                system_prompt=system_prompt,
                user_message=user_message,
                pipeline_id=pipeline_id,
                pipeline_type=pipeline_type,
                entity=entity,
            )

        start = time.monotonic()
        try:
            response = await self._call_llm(messages)
            duration_ms = int((time.monotonic() - start) * 1000)
            text = response.choices[0].message.content or ""

            if self._run_logger:
                usage = response.usage or {}
                await self._run_logger.llm_response_ok(
                    agent_id=agent_id,
                    prompt_title=prompt_title,
                    duration_ms=duration_ms,
                    tokens={
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage, "completion_tokens", 0),
                        "total_tokens": getattr(usage, "total_tokens", 0),
                    },
                    response_text=text,
                    pipeline_id=pipeline_id,
                    pipeline_type=pipeline_type,
                    entity=entity,
                )
            return text
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            if self._run_logger:
                await self._run_logger.llm_response_error(
                    agent_id=agent_id,
                    prompt_title=prompt_title,
                    duration_ms=duration_ms,
                    error=str(exc),
                    pipeline_id=pipeline_id,
                    pipeline_type=pipeline_type,
                    entity=entity,
                )
            logger.error("LLM completion failed after retries", exc_info=True)
            raise LLMError(str(exc)) from exc

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_handlers: dict[str, Callable[..., Awaitable[str]]],
        max_tool_rounds: int = 5,
        log_context: dict[str, Any] | None = None,
    ) -> str:
        """Send a completion request that may invoke tools in a loop."""
        ctx = log_context or {}
        agent_id = ctx.get("agent_id", "")
        prompt_title = ctx.get("prompt_title", "")
        pipeline_id = ctx.get("pipeline_id", "")
        pipeline_type = ctx.get("pipeline_type", "")
        entity = ctx.get("entity", "")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        try:
            for round_num in range(max_tool_rounds):
                if self._run_logger:
                    round_title = f"{prompt_title} (round {round_num + 1})" if prompt_title else f"round {round_num + 1}"
                    await self._run_logger.llm_request(
                        agent_id=agent_id,
                        prompt_title=round_title,
                        model=self._model,
                        system_prompt=system_prompt,
                        user_message=json.dumps(messages[-1].get("content", "")),
                        pipeline_id=pipeline_id,
                        pipeline_type=pipeline_type,
                        entity=entity,
                    )

                start = time.monotonic()
                try:
                    response = await self._call_llm(messages, tools=tools, tool_choice="auto")
                    duration_ms = int((time.monotonic() - start) * 1000)
                except Exception as exc:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    if self._run_logger:
                        await self._run_logger.llm_response_error(
                            agent_id=agent_id,
                            prompt_title=prompt_title,
                            duration_ms=duration_ms,
                            error=str(exc),
                            pipeline_id=pipeline_id,
                            pipeline_type=pipeline_type,
                            entity=entity,
                        )
                    raise

                msg = response.choices[0].message

                if not msg.tool_calls:
                    if self._run_logger:
                        usage = response.usage or {}
                        await self._run_logger.llm_response_ok(
                            agent_id=agent_id,
                            prompt_title=prompt_title,
                            duration_ms=duration_ms,
                            tokens={
                                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                                "completion_tokens": getattr(usage, "completion_tokens", 0),
                                "total_tokens": getattr(usage, "total_tokens", 0),
                            },
                            response_text=msg.content or "",
                            pipeline_id=pipeline_id,
                            pipeline_type=pipeline_type,
                            entity=entity,
                        )
                    return msg.content or ""

                logger.info(
                    "LLM requested tool calls",
                    extra={"round": round_num + 1, "tools": [tc.function.name for tc in msg.tool_calls]},
                )

                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        args: dict[str, Any] = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    if tool_name in tool_handlers:
                        result = await tool_handlers[tool_name](**args)
                    else:
                        result = f"Unknown tool: {tool_name}"
                        logger.warning("Unknown tool called by LLM", extra={"tool": tool_name})

                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            logger.warning("Tool-use loop reached max rounds without final answer", extra={"max_rounds": max_tool_rounds})
            last_content = response.choices[0].message.content  # type: ignore[possibly-undefined]
            return last_content or ""

        except LLMError:
            raise
        except Exception as exc:
            logger.error("LLM tool-use completion failed", exc_info=True)
            raise LLMError(str(exc)) from exc

    @retry(
        stop=stop_after_attempt(settings.llm_max_retries),
        wait=wait_random_exponential(min=5, max=60),
        retry=retry_if_exception_type((litellm.RateLimitError, litellm.Timeout)),
    )
    async def _call_llm(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        """Single LLM call with retry on rate-limit or timeout errors."""
        if settings.llm_request_delay_seconds > 0:
            await asyncio.sleep(settings.llm_request_delay_seconds)

        params: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "timeout": settings.llm_timeout_seconds,
            "response_format": {"type": "json_object"},
            **kwargs,
        }
        if self._base_url:
            params["base_url"] = self._base_url
        if self._api_key:
            params["api_key"] = self._api_key

        return await litellm.acompletion(**params)
