from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from tavily import AsyncTavilyClient

from ai_service.config import settings
from ai_service.schemas.search import SearchResponse, SearchResultItem
from ai_service.utils.logger import get_logger
from ai_service.utils.run_logger import RunLogger

logger = get_logger(__name__)


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
        if settings.search_enabled and settings.tavily_api_key:
            self._client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    def is_available(self) -> bool:
        return self._client is not None

    async def search(
        self,
        query: str,
        *,
        ticker: str = "",
        agent_id: str = "",
        prompt_title: str = "",
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
            )

        start = time.monotonic()
        try:
            raw: dict[str, Any] = await self._client.search(
                query=query,
                search_depth=settings.search_depth,
                max_results=settings.search_max_results,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            items = [
                SearchResultItem(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=float(r.get("score", 0.0)),
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
                )

            return _format_context(response)
        except Exception as exc:
            logger.warning(
                "Tavily search failed — continuing without search context",
                extra={**extra, "error": str(exc)},
            )
            return ""


def _format_context(response: SearchResponse) -> str:
    """Format a SearchResponse as a plain-text block for LLM injection."""
    lines: list[str] = [
        "--- LIVE WEB SEARCH CONTEXT ---",
        f'Query: "{response.query}"',
        f"Retrieved: {response.retrieved_at}",
        "",
    ]
    for i, item in enumerate(response.results, start=1):
        domain = urlparse(item.url).netloc or item.url
        snippet = item.content[:400].rstrip()
        if len(item.content) > 400:
            snippet += "..."
        lines += [
            f"[{i}] {item.title}",
            f"    Source: {domain}",
            f"    {snippet}",
            "",
        ]
    lines.append("--- END SEARCH CONTEXT ---")
    return "\n".join(lines)
