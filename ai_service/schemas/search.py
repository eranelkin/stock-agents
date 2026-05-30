from __future__ import annotations

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    title: str
    url: str
    content: str
    score: float = 0.0


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    retrieved_at: str
