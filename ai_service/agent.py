from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import jsonschema

from ai_service.config import settings
from ai_service.models.llm_client import LLMClient, LLMError
from ai_service.models.search_client import SearchClient
from ai_service.utils.logger import get_logger
from ai_service.utils.run_logger import RunLogger
from ai_service.utils.search_tool import WEB_SEARCH_TOOL, execute_search

logger = get_logger(__name__)

# Number of times to retry an LLM call when the response fails schema validation.
_SCHEMA_RETRY_ATTEMPTS = 3


def _parse_response(raw: str) -> dict[str, Any]:
    """Parse LLM response as JSON.

    With response_format=json_object the provider guarantees valid JSON, so
    direct json.loads is almost always sufficient. The code-block fallback
    handles the rare edge case where a model wraps the JSON in markdown fences
    despite the constraint (observed on a small number of local/open models).
    """
    text = raw.strip()

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: extract content from ```json or ``` fences
    match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1).strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError("Response is not parseable as JSON")


def _validate_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate data against a JSON Schema. Returns list of error messages (empty = valid)."""
    try:
        jsonschema.validate(instance=data, schema=schema)
        return []
    except jsonschema.ValidationError as exc:
        return [exc.message]
    except jsonschema.SchemaError as exc:
        logger.warning("Output schema itself is invalid: %s", exc.message)
        return []  # Don't block the pipeline on a malformed schema definition


def _build_schema_section(label: str, schema: dict[str, Any]) -> str:
    """Format a schema dict as a readable JSON block for injection into the system prompt."""
    return f"\n\n--- {label} ---\n{json.dumps(schema, indent=2)}\n---"


def _resolve_placeholders(text: str) -> str:
    """Replace known placeholders in a prompt string before sending to the LLM."""
    now = datetime.now(ZoneInfo("America/New_York"))
    current_date = now.strftime(f"%B {now.day}, %Y, %H:%M %Z")
    return text.replace("{CURRENT_DATE}", current_date)


def _build_system_prompt(
    base_prompt: str,
    output_schema: dict[str, Any] | None,
    input_schema: dict[str, Any] | None,
) -> str:
    """Append schema sections to the system prompt when schemas are defined."""
    prompt = base_prompt
    if input_schema:
        prompt += _build_schema_section("INPUT SCHEMA — what you will receive", input_schema)
    if output_schema:
        prompt += _build_schema_section(
            "OUTPUT SCHEMA — respond ONLY with a JSON object that matches this schema exactly. No explanation, no text before or after, no markdown. Pure JSON only.",
            output_schema,
        )
    return prompt


class Agent:
    """Stateless agent: receives a prompt + entity input, calls LLM, returns JSON."""

    def __init__(
        self,
        agent_id: str,
        prompt: str,
        llm_client: LLMClient,
        run_logger: RunLogger | None = None,
        search_mode: str | None = None,
        output_schema: dict[str, Any] | None = None,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.prompt = prompt
        self._llm = llm_client
        self._run_logger = run_logger
        self._search_mode = search_mode
        self._output_schema = output_schema
        self._input_schema = input_schema

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
        """Execute the agent and return a parsed, schema-validated JSON dict."""
        extra = {"ticker": ticker, "agent_id": self.agent_id, "pipeline_id": pipeline_id}

        user_content: dict[str, Any] = dict(ticker_input)
        if previous_output is not None:
            user_content["previous_output"] = previous_output

        full_log_context = {
            "agent_id": self.agent_id,
            "prompt_title": prompt_title,
            **(log_context or {}),
        }

        resolved_base = _resolve_placeholders(self.prompt)
        system_prompt = _build_system_prompt(resolved_base, self._output_schema, self._input_schema)
        effective_search_mode = self._search_mode or settings.search_mode

        try:
            if effective_search_mode == "tool_call":
                search_handler = self._make_search_handler(
                    ticker=ticker,
                    prompt_title=prompt_title,
                    pipeline_id=pipeline_id,
                    pipeline_type=(log_context or {}).get("pipeline_type", ""),
                )
                raw = await self._llm.complete_with_tools(
                    system_prompt=system_prompt,
                    user_message=json.dumps(user_content),
                    tools=[WEB_SEARCH_TOOL],
                    tool_handlers={"web_search": search_handler},
                    max_tool_rounds=settings.search_max_tool_rounds,
                    log_context=full_log_context,
                )
                return self._parse_and_validate(raw, extra)
            else:
                if search_context:
                    user_content["search_context"] = search_context
                return await self._run_with_schema_retry(
                    system_prompt=system_prompt,
                    user_message=json.dumps(user_content),
                    log_context=full_log_context,
                    extra=extra,
                )

        except LLMError as exc:
            logger.error("Agent LLM call failed", exc_info=True, extra=extra)
            return {"error": str(exc), "parse_error": True}

    async def _run_with_schema_retry(
        self,
        system_prompt: str,
        user_message: str,
        log_context: dict[str, Any],
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        """Call the LLM and retry up to _SCHEMA_RETRY_ATTEMPTS times on schema mismatch."""
        last_result: dict[str, Any] = {"raw_output": "", "parse_error": True}

        for attempt in range(1, _SCHEMA_RETRY_ATTEMPTS + 1):
            raw = await self._llm.complete(
                system_prompt=system_prompt,
                user_message=user_message,
                log_context=log_context,
            )
            result = self._parse_and_validate(raw, extra)

            # If parse failed, no point retrying — response_format guarantees JSON;
            # a parse failure here means something very unusual happened
            if result.get("parse_error"):
                return result

            # No schema defined or validation passed
            if not self._output_schema or not result.get("schema_error"):
                return result

            # Schema mismatch — log and retry
            logger.warning(
                "Schema validation failed (attempt %d/%d): %s",
                attempt,
                _SCHEMA_RETRY_ATTEMPTS,
                result.get("schema_errors", []),
                extra=extra,
            )
            last_result = result

        logger.warning(
            "Schema validation failed after %d attempts — returning last result",
            _SCHEMA_RETRY_ATTEMPTS,
            extra=extra,
        )
        return last_result

    def _parse_and_validate(self, raw: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Parse raw LLM text to dict and validate against output_schema if set."""
        try:
            result = _parse_response(raw)
        except ValueError as exc:
            logger.warning("Agent output parse failed", extra={**extra, "error": str(exc)})
            return {"raw_output": raw, "parse_error": True}

        if self._output_schema:
            errors = _validate_schema(result, self._output_schema)
            if errors:
                return {**result, "schema_error": True, "schema_errors": errors}

        return result

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
