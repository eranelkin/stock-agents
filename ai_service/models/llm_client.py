from __future__ import annotations

import asyncio
import json
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

logger = get_logger(__name__)


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class LLMClient:
    """Provider-agnostic async LLM client backed by litellm.acompletion."""

    def __init__(self, model_config: ModelConfig) -> None:
        self._model = model_config.model_id
        self._base_url = model_config.base_url
        self._api_key = model_config.api_key

    async def complete(self, system_prompt: str, user_message: str) -> str:
        """Send a chat completion and return the response text.

        Args:
            system_prompt: Content for the system role.
            user_message: Content for the user role.

        Returns:
            Raw response string from the model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        try:
            response = await self._call_llm(messages)
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM completion failed after retries", exc_info=True)
            raise LLMError(str(exc)) from exc

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_handlers: dict[str, Callable[..., Awaitable[str]]],
        max_tool_rounds: int = 5,
    ) -> str:
        """Send a completion request that may invoke tools in a loop.

        The LLM may call one or more tools per round. Each tool result is fed
        back until the model returns a plain content response or max_tool_rounds
        is exhausted.

        Args:
            system_prompt: Content for the system role.
            user_message: Content for the user role.
            tools: List of tool definitions in OpenAI function-calling format.
            tool_handlers: Mapping of tool name → async callable that executes it.
            max_tool_rounds: Maximum number of tool-call/result round trips.

        Returns:
            Final response string from the model.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        try:
            for round_num in range(max_tool_rounds):
                response = await self._call_llm(messages, tools=tools, tool_choice="auto")
                msg = response.choices[0].message

                if not msg.tool_calls:
                    return msg.content or ""

                logger.info(
                    "LLM requested tool calls",
                    extra={"round": round_num + 1, "tools": [tc.function.name for tc in msg.tool_calls]},
                )

                # Append the assistant's tool-call message
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                # Execute each tool and append results
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

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

            # max rounds reached without a final answer — return whatever we have
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
        """Single LLM call with retry on rate-limit or timeout errors.

        Args:
            messages: Full messages list to send.
            **kwargs: Extra params forwarded to litellm (e.g. tools, tool_choice).

        Returns:
            litellm ModelResponse object.
        """
        if settings.llm_request_delay_seconds > 0:
            await asyncio.sleep(settings.llm_request_delay_seconds)

        params: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "timeout": settings.llm_timeout_seconds,
            **kwargs,
        }
        if self._base_url:
            params["base_url"] = self._base_url
        if self._api_key:
            params["api_key"] = self._api_key

        return await litellm.acompletion(**params)
