from __future__ import annotations

import json
from typing import Any

from ai_service.config import settings
from ai_service.models.llm_client import LLMClient, LLMError
from ai_service.utils.logger import get_logger
from ai_service.utils.search_tool import WEB_SEARCH_TOOL, execute_search

logger = get_logger(__name__)


class Agent:
    """Stateless agent: receives a prompt + entity input, calls LLM, returns JSON."""

    def __init__(self, agent_id: str, prompt: str, llm_client: LLMClient) -> None:
        self.agent_id = agent_id
        self.prompt = prompt
        self._llm = llm_client

    async def run(
        self,
        ticker_input: dict[str, Any],
        previous_output: dict[str, Any] | None = None,
        *,
        ticker: str = "",
        pipeline_id: str = "",
        search_context: str = "",
        prompt_title: str = "",
        log_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the agent and return a parsed JSON dict."""
        extra = {"ticker": ticker, "agent_id": self.agent_id, "pipeline_id": pipeline_id}
        user_content: dict[str, Any] = dict(ticker_input)
        if previous_output is not None:
            user_content["previous_output"] = previous_output

        full_log_context = {
            "agent_id": self.agent_id,
            "prompt_title": prompt_title,
            **(log_context or {}),
        }

        raw = ""
        try:
            if settings.search_mode == "tool_call":
                raw = await self._llm.complete_with_tools(
                    system_prompt=self.prompt,
                    user_message=json.dumps(user_content),
                    tools=[WEB_SEARCH_TOOL],
                    tool_handlers={"web_search": execute_search},
                    log_context=full_log_context,
                )
            else:
                if search_context:
                    user_content["search_context"] = search_context
                raw = await self._llm.complete(
                    system_prompt=self.prompt,
                    user_message=json.dumps(user_content),
                    log_context=full_log_context,
                )

            result: dict[str, Any] = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError(f"Expected JSON object, got {type(result).__name__}")
            return result
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Agent output parse failed", extra={**extra, "error": str(exc)})
            return {"raw_output": raw, "parse_error": True}
        except LLMError as exc:
            logger.error("Agent LLM call failed", exc_info=True, extra=extra)
            return {"error": str(exc), "parse_error": True}
