from __future__ import annotations

from ai_service.models.search_client import SearchClient

WEB_SEARCH_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for up-to-date information about a stock, company, "
            "or financial topic. Use this when you need current prices, news, or "
            "recent analyst reports that may not be in your training data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                }
            },
            "required": ["query"],
        },
    },
}

_client = SearchClient()


async def execute_search(query: str) -> str:
    """Execute a web search via Tavily and return a formatted context block.

    Args:
        query: Search query string from the LLM tool call.

    Returns:
        Formatted plain-text search results, or an empty string if unavailable.
    """
    return await _client.search(query)
