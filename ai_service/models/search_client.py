from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from tavily import AsyncTavilyClient

from ai_service.config import settings
from ai_service.schemas.search import SearchResponse, SearchResultItem
from ai_service.utils.backend_client import notify_run_alert
from ai_service.utils.logger import get_logger
from ai_service.utils.market_calendar import last_market_close
from ai_service.utils.run_logger import RunLogger
from ai_service.utils.tavily_key_pool import get_tavily_key_pool

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")


def build_search_query(ticker: str, template: str | None = None) -> str:
    """Return a Tavily search query for the given ticker."""
    if template:
        return template.format(ticker=ticker)
    year = datetime.now(timezone.utc).year
    return f"{ticker} stock latest news research {year}"


class SearchClient:
    """Async Tavily search wrapper with graceful degradation."""

    def __init__(self, run_logger: RunLogger | None = None) -> None:
        self._client: AsyncTavilyClient | None = None
        self._run_logger = run_logger
        self._key_pool = get_tavily_key_pool()
        current_key = self._key_pool.current_key()
        if settings.search_enabled and current_key:
            self._client = AsyncTavilyClient(api_key=current_key)

    def is_available(self) -> bool:
        return self._client is not None

    async def search(
        self,
        query: str,
        *,
        ticker: str = "",
        agent_id: str = "",
        prompt_title: str = "",
        pipeline_id: str = "",
        pipeline_type: str = "",
        search_depth: str | None = None,
    ) -> str:
        """Run a Tavily search and return a formatted plain-text context block."""
        if not self._client:
            return ""

        extra = {"ticker": ticker, "agent_id": agent_id, "query": query}

        if self._run_logger:
            await self._run_logger.search_request(
                agent_id=agent_id,
                prompt_title=prompt_title,
                query=query,
                pipeline_id=pipeline_id,
                pipeline_type=pipeline_type,
                entity=ticker,
            )

        # Freshness filter: prefer the exact last-NYSE-close window (day-granularity
        # on Tavily's side — the precise 16:00 boundary is enforced at the prompt
        # level, see _format_context below) over the flat rolling `days` window.
        # This is a rollback switch, not a per-call choice, so every search-enabled
        # agent gets the same behavior consistently.
        freshness_params: dict[str, Any]
        if settings.search_since_last_close_enabled:
            freshness_params = {
                "start_date": last_market_close().date().isoformat(),
                "end_date": datetime.now(_ET).date().isoformat(),
            }
        else:
            freshness_params = {"days": settings.search_days}

        attempts_left = max(1, self._key_pool.total_keys)
        while attempts_left > 0:
            attempts_left -= 1
            start = time.monotonic()
            try:
                raw: dict[str, Any] = await self._client.search(
                    query=query,
                    search_depth=search_depth or settings.search_depth,
                    max_results=settings.search_max_results,
                    # "news" topic: (a) makes Tavily's date filters actually apply
                    # server-side (per Tavily's docs, day-based filters are only
                    # honored for the news topic, not "general"), and (b) makes
                    # published_date far more reliably populated, since Tavily's
                    # news pipeline tracks publish dates explicitly.
                    topic="news",
                    **freshness_params,
                )
                duration_ms = int((time.monotonic() - start) * 1000)
                items = [
                    SearchResultItem(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        content=r.get("content", ""),
                        score=float(r.get("score", 0.0)),
                        published_date=r.get("published_date"),
                    )
                    for r in raw.get("results", [])
                ]
                response = SearchResponse(
                    query=query,
                    results=items,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                )
                logger.info("Tavily search succeeded", extra={**extra, "result_count": len(items)})

                if self._run_logger:
                    sources = [
                        f"{item.title} — {urlparse(item.url).netloc or item.url}"
                        for item in items
                    ]
                    await self._run_logger.search_response(
                        agent_id=agent_id,
                        prompt_title=prompt_title,
                        duration_ms=duration_ms,
                        sources=sources,
                        pipeline_id=pipeline_id,
                        pipeline_type=pipeline_type,
                        entity=ticker,
                    )

                return _format_context(response)
            except Exception as exc:
                if _is_quota_or_rate_limit_error(exc):
                    logger.error("Tavily key exhausted or rate-limited", extra={**extra, "error": str(exc)})
                    rotation = await self._key_pool.mark_exhausted_and_rotate()
                    if rotation and attempts_left > 0:
                        next_key, exhausted_index, next_index = rotation
                        self._client = AsyncTavilyClient(api_key=next_key)
                        if self._run_logger:
                            await self._run_logger.key_switch(
                                agent_id=agent_id,
                                prompt_title=prompt_title,
                                exhausted_index=exhausted_index,
                                next_index=next_index,
                                total_keys=self._key_pool.total_keys,
                                reason=str(exc),
                                pipeline_id=pipeline_id,
                                pipeline_type=pipeline_type,
                                entity=ticker,
                            )
                        continue

                    if self._run_logger:
                        await self._run_logger.search_error(
                            agent_id=agent_id,
                            prompt_title=prompt_title,
                            error=str(exc),
                            pipeline_id=pipeline_id,
                            pipeline_type=pipeline_type,
                            entity=ticker,
                        )
                        await notify_run_alert(
                            self._run_logger.run_id,
                            f"All {self._key_pool.total_keys} Tavily API keys are quota/rate-limit "
                            f"exhausted — News/Macro agents are running without live search context "
                            f"until this is resolved. ({exc})",
                        )
                    return ""
                else:
                    logger.warning(
                        "Tavily search failed — continuing without search context",
                        extra={**extra, "error": str(exc)},
                    )
                    return ""
        return ""


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
    """Return True if this Tavily error means the current key is spent (quota or rate limit)."""
    text = str(exc).lower()
    return (
        "plan's set usage limit" in text
        or "rate limit" in text
        or "429" in text
        or "usage limit" in text
    )


def _format_context(response: SearchResponse) -> str:
    """Format a SearchResponse as a plain-text block for LLM injection."""
    cutoff = last_market_close()
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M %Z")
    lines: list[str] = [
        "--- LIVE WEB SEARCH CONTEXT ---",
        f'Query: "{response.query}"',
        f"Retrieved: {response.retrieved_at}",
        f"Last market close cutoff: {cutoff_str}  <- EXCLUDE any article whose event/publish date is before this",
        "",
    ]
    for i, item in enumerate(response.results, start=1):
        domain = urlparse(item.url).netloc or item.url
        snippet = item.content[:400].rstrip()
        if len(item.content) > 400:
            snippet += "..."
        date_line = f"    Published: {item.published_date}" if item.published_date else "    Published: unknown"
        lines += [
            f"[{i}] {item.title}",
            f"    Source: {domain}",
            date_line,
            f"    {snippet}",
            "",
        ]
    lines.append("--- END SEARCH CONTEXT ---")
    return "\n".join(lines)
