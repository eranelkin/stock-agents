from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiofiles

_SEP_RUN = "=" * 80
_SEP_PIPE = "-" * 80
_PROMPT_TRUNCATE = 400


@dataclass
class _Stats:
    llm_calls: int = 0
    llm_errors: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RunLogger:
    """Writes a human-readable structured log file for one orchestrator run.

    All public methods are coroutines. An asyncio.Lock serialises writes so
    concurrent pipelines never interleave log lines.
    """

    def __init__(self, log_path: str) -> None:
        self._path = log_path
        self._lock = asyncio.Lock()
        self._stats = _Stats()
        self._file: Any = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def open(self, run_id: str, started_at: str) -> None:
        """Create the log file and write the file header. Call once before any log method."""
        self._file = await aiofiles.open(self._path, "w", encoding="utf-8")
        header = (
            f"{_SEP_RUN}\n"
            f" STOCK-AGENTS  ·  RUN LOG\n"
            f"{_SEP_RUN}\n"
            f" Run ID   :  {run_id}\n"
            f" Started  :  {started_at}\n"
            f"{_SEP_RUN}\n\n\n"
        )
        await self._write(header)

    async def close(self) -> None:
        """Flush and close the log file."""
        if self._file:
            async with self._lock:
                await self._file.close()
                self._file = None

    # ── Run-level events ───────────────────────────────────────────────────────

    async def run_start(
        self,
        *,
        mode: str,
        models: list[str],
        tickers: list[str],
        agent_prompts: list[str],
        sector_prompts: list[str],
    ) -> None:
        model_str = ", ".join(models) if models else "—"
        ticker_str = ", ".join(tickers) if tickers else "—"
        agent_str = (
            f"{', '.join(agent_prompts)}  [{len(agent_prompts)}]"
            if agent_prompts else "none"
        )
        sector_str = (
            f"{', '.join(sector_prompts)}  [{len(sector_prompts)}]"
            if sector_prompts else "none"
        )
        text = (
            f"== RUN STARTED {'=' * (80 - 16)}\n"
            f"  Models   :  {model_str}\n"
            f"  Tickers  :  {ticker_str}  [{len(tickers)}]\n"
            f"  Agents   :  {agent_str}\n"
            f"  Sectors  :  {sector_str}\n"
            f"  Mode     :  {mode}\n\n\n"
        )
        await self._write(text)

    async def run_end(self, *, total_duration_ms: int) -> None:
        s = self._stats
        success = s.llm_calls - s.llm_errors
        text = (
            f"\n\n== RUN COMPLETED {'=' * (80 - 17)}\n"
            f"  Total duration  :  {total_duration_ms:,}ms\n"
            f"  LLM calls       :  {s.llm_calls} total  ·  {success} success  ·  {s.llm_errors} error\n"
            f"  Total tokens    :  prompt={s.prompt_tokens:,}  completion={s.completion_tokens:,}  total={s.total_tokens:,}\n"
            f"{_SEP_RUN}\n"
        )
        await self._write(text)

    # ── Pipeline-level events ──────────────────────────────────────────────────

    async def pipeline_start(
        self,
        *,
        pipeline_type: str,
        entity: str,
        model: str,
        pipeline_id: str,
    ) -> None:
        label = f"  {pipeline_type} / {entity} / {model}  "
        dashes = "-" * max(0, 80 - len(label) - 4)
        text = (
            f"\n{_SEP_PIPE}\n"
            f"  PIPELINE STARTED  |  {pipeline_type} / {entity} / {model}\n"
            f"  pipeline_id :  {pipeline_id}\n"
            f"{_SEP_PIPE}\n\n"
        )
        await self._write(text)

    async def pipeline_end(
        self,
        *,
        pipeline_type: str,
        entity: str,
        model: str,
        pipeline_id: str,
        duration_ms: int,
        output_file: str,
    ) -> None:
        text = (
            f"\n{_SEP_PIPE}\n"
            f"  PIPELINE COMPLETED  |  {pipeline_type} / {entity} / {model}  ({duration_ms:,}ms)\n"
            f"  pipeline_id :  {pipeline_id}\n"
            f"  output      :  {output_file}\n"
            f"{_SEP_PIPE}\n\n"
        )
        await self._write(text)

    # ── Agent-level events ─────────────────────────────────────────────────────

    async def search_request(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        query: str,
    ) -> None:
        text = (
            f"  {self._ts()}  SEARCH REQUEST  |  {prompt_title}\n"
            f"    agent_id :  {agent_id}\n"
            f"    query    :  \"{query}\"\n\n"
        )
        await self._write(text)

    async def search_response(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        duration_ms: int,
        sources: list[str],
    ) -> None:
        source_lines = "".join(
            f"      [{i + 1}] {s}\n" for i, s in enumerate(sources)
        )
        text = (
            f"  {self._ts()}  SEARCH RESPONSE  |  {prompt_title}\n"
            f"    agent_id :  {agent_id}\n"
            f"    duration :  {duration_ms:,}ms   |   results : {len(sources)}\n"
            f"    sources  :\n"
            f"{source_lines}\n"
        )
        await self._write(text)

    async def llm_request(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        model: str,
        system_prompt: str,
        user_message: str,
    ) -> None:
        if len(system_prompt) > _PROMPT_TRUNCATE:
            prompt_display = (
                system_prompt[:_PROMPT_TRUNCATE].replace("\n", "\n                ")
                + f"\n                ... [{len(system_prompt)} chars total]"
            )
        else:
            prompt_display = system_prompt.replace("\n", "\n                ")

        text = (
            f"  {self._ts()}  LLM REQUEST  |  {prompt_title}\n"
            f"    agent_id :  {agent_id}\n"
            f"    model    :  {model}\n"
            f"    prompt   :  {prompt_display}\n"
            f"    input    :  {user_message}\n\n"
        )
        await self._write(text)

    async def llm_response_ok(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        duration_ms: int,
        tokens: dict[str, int],
        response_text: str,
    ) -> None:
        self._stats.llm_calls += 1
        pt = tokens.get("prompt_tokens", 0)
        ct = tokens.get("completion_tokens", 0)
        tt = tokens.get("total_tokens", 0)
        self._stats.prompt_tokens += pt
        self._stats.completion_tokens += ct
        self._stats.total_tokens += tt

        try:
            formatted = json.dumps(json.loads(response_text), indent=2, ensure_ascii=False)
            response_display = "\n".join(f"      {line}" for line in formatted.splitlines())
        except (json.JSONDecodeError, ValueError):
            response_display = f"      {response_text}"

        token_str = f"prompt={pt:,}  completion={ct:,}  total={tt:,}" if tt else "not reported"
        text = (
            f"  {self._ts()}  LLM RESPONSE  |  {prompt_title}  [SUCCESS]\n"
            f"    agent_id :  {agent_id}\n"
            f"    duration :  {duration_ms:,}ms\n"
            f"    tokens   :  {token_str}\n"
            f"    response :\n"
            f"{response_display}\n\n"
        )
        await self._write(text)

    async def llm_response_error(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        duration_ms: int,
        error: str,
    ) -> None:
        self._stats.llm_calls += 1
        self._stats.llm_errors += 1
        text = (
            f"  {self._ts()}  LLM RESPONSE  |  {prompt_title}  [ERROR]\n"
            f"    agent_id :  {agent_id}\n"
            f"    duration :  {duration_ms:,}ms\n"
            f"    error    :  {error}\n\n"
        )
        await self._write(text)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _ts(self) -> str:
        """Return current UTC time as [HH:MM:SS.mmm]."""
        now = datetime.now(timezone.utc)
        return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"

    async def _write(self, text: str) -> None:
        if not self._file:
            return
        async with self._lock:
            await self._file.write(text)
