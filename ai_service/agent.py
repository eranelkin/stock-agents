from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from ai_service.config import settings
from ai_service.models.llm_client import LLMClient, LLMError
from ai_service.models.search_client import SearchClient
from ai_service.utils.logger import get_logger
from ai_service.utils.run_logger import RunLogger
from ai_service.utils.search_tool import WEB_SEARCH_TOOL, execute_search

logger = get_logger(__name__)


def _quote_yaml_values(text: str) -> str:
    """Quote unquoted block-mapping values that contain ': ' (colon-space).

    PyYAML's scanner treats ': ' inside a plain scalar as a new mapping-key
    indicator, raising YAMLError. This pass wraps such values in double quotes
    so the second parse attempt succeeds.
    """
    lines = []
    for line in text.split('\n'):
        m = re.match(r'^(\s+)(.+?):\s(.+)$', line)
        if m:
            indent, key, val = m.group(1), m.group(2), m.group(3)
            if val and val[0] not in ('"', "'", '{', '[', '|', '>') and ': ' in val:
                escaped = val.replace('\\', '\\\\').replace('"', '\\"')
                line = f'{indent}{key}: "{escaped}"'
        lines.append(line)
    return '\n'.join(lines)


def _parse_response(raw: str) -> dict[str, Any]:
    """Try JSON → YAML → sanitised YAML → code-block → prose-stripped YAML. Raises ValueError if all fail."""
    text = raw.strip()

    # 1. Try JSON directly
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Try YAML directly
    try:
        result = yaml.safe_load(text)
        if isinstance(result, dict):
            return result
    except yaml.YAMLError:
        pass

    # 2b. YAML failed — quote values containing ': ' and retry.
    # LLMs commonly write plain scalars like "3 scenarios: Bull 50% / Bear 15%"
    # which PyYAML rejects because ': ' looks like a mapping key indicator.
    try:
        result = yaml.safe_load(_quote_yaml_values(text))
        if isinstance(result, dict):
            return result
    except yaml.YAMLError:
        pass

    # 3. Extract content from ```json or ```yaml code blocks and retry
    match = re.search(r"```(?:json|yaml)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        block = match.group(1).strip()
        try:
            result = json.loads(block)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            result = yaml.safe_load(block)
            if isinstance(result, dict):
                return result
        except yaml.YAMLError:
            pass

    # 4. LLM prefixed narrative prose before the actual YAML data (no code fences).
    #    Scan for lines that look like top-level YAML mapping keys and try parsing
    #    from each match position. Covers the common "think-then-dump-YAML" pattern.
    for m in re.finditer(r'^[a-z_][a-zA-Z0-9_]*:\s*', text, re.MULTILINE):
        candidate = text[m.start():]
        if candidate.count('\n') < 2:
            continue
        for attempt in (candidate, _quote_yaml_values(candidate)):
            try:
                result = yaml.safe_load(attempt)
                if isinstance(result, dict):
                    return result
            except yaml.YAMLError:
                pass

    raise ValueError("Response is not parseable as JSON or YAML")


def _resolve_placeholders(text: str) -> str:
    """Replace known placeholders in a prompt string before sending to the LLM."""
    now = datetime.now(ZoneInfo("America/New_York"))
    current_date = now.strftime(f"%B {now.day}, %Y, %H:%M %Z")
    return text.replace("{CURRENT_DATE}", current_date)


class Agent:
    """Stateless agent: receives a prompt + entity input, calls LLM, returns JSON."""

    def __init__(
        self,
        agent_id: str,
        prompt: str,
        llm_client: LLMClient,
        run_logger: RunLogger | None = None,
        search_mode: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.prompt = prompt
        self._llm = llm_client
        self._run_logger = run_logger
        self._search_mode = search_mode

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

        resolved_prompt = _resolve_placeholders(self.prompt)
        effective_search_mode = self._search_mode or settings.search_mode
        raw = ""
        try:
            if effective_search_mode == "tool_call":
                search_handler = self._make_search_handler(
                    ticker=ticker,
                    prompt_title=prompt_title,
                    pipeline_id=pipeline_id,
                    pipeline_type=(log_context or {}).get("pipeline_type", ""),
                )
                raw = await self._llm.complete_with_tools(
                    system_prompt=resolved_prompt,
                    user_message=json.dumps(user_content),
                    tools=[WEB_SEARCH_TOOL],
                    tool_handlers={"web_search": search_handler},
                    max_tool_rounds=settings.search_max_tool_rounds,
                    log_context=full_log_context,
                )
            else:
                if search_context:
                    user_content["search_context"] = search_context
                raw = await self._llm.complete(
                    system_prompt=resolved_prompt,
                    user_message=json.dumps(user_content),
                    log_context=full_log_context,
                )

            return _parse_response(raw)
        except ValueError as exc:
            logger.warning("Agent output parse failed", extra={**extra, "error": str(exc)})
            return {"raw_output": raw, "parse_error": True}
        except LLMError as exc:
            logger.error("Agent LLM call failed", exc_info=True, extra=extra)
            return {"error": str(exc), "parse_error": True}

    def _make_search_handler(
        self,
        *,
        ticker: str,
        prompt_title: str,
        pipeline_id: str,
        pipeline_type: str,
    ):
        """Return a search coroutine that logs via RunLogger when available."""
        client = SearchClient(run_logger=self._run_logger)
        agent_id = self.agent_id

        async def _handler(query: str) -> str:
            return await client.search(
                query,
                ticker=ticker,
                agent_id=agent_id,
                prompt_title=prompt_title,
                pipeline_id=pipeline_id,
                pipeline_type=pipeline_type,
            )

        return _handler
