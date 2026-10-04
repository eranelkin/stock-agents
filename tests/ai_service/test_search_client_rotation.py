from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_service.config import settings
from ai_service.models import search_client as search_client_module
from ai_service.models.search_client import SearchClient
from ai_service.utils import tavily_key_pool as key_pool_module


class FakeTavilyClient:
    """Stand-in for AsyncTavilyClient whose .search() is scripted per call."""

    def __init__(self, api_key: str, script: list) -> None:
        self.api_key = api_key
        self._script = script
        self.calls: list[str] = []

    async def search(self, **kwargs):
        self.calls.append(self.api_key)
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def _isolated_key_pool(monkeypatch):
    """Give each test a fresh key pool + enabled search, torn down after."""
    monkeypatch.setattr(key_pool_module, "_pool", None)
    original_enabled = settings.search_enabled
    original_keys = settings.tavily_api_keys
    settings.search_enabled = True
    yield
    settings.search_enabled = original_enabled
    settings.tavily_api_keys = original_keys
    monkeypatch.setattr(key_pool_module, "_pool", None)


def _quota_error() -> Exception:
    return Exception("You have reached your plan's set usage limit.")


async def test_search_rotates_to_next_key_on_quota_error_and_succeeds():
    settings.tavily_api_keys = "key-1,key-2"
    fakes = {
        "key-1": FakeTavilyClient("key-1", [_quota_error()]),
        "key-2": FakeTavilyClient("key-2", [{"results": [{"title": "t", "url": "u", "content": "c", "score": 0.9, "published_date": "2026-09-26"}]}]),
    }

    def factory(api_key: str):
        return fakes[api_key]

    with patch.object(search_client_module, "AsyncTavilyClient", side_effect=factory):
        client = SearchClient()
        result = await client.search("AAPL news")

    assert "t" in result
    assert fakes["key-1"].calls == ["key-1"]
    assert fakes["key-2"].calls == ["key-2"]


async def test_search_returns_empty_when_all_keys_exhausted():
    settings.tavily_api_keys = "key-1,key-2"
    fakes = {
        "key-1": FakeTavilyClient("key-1", [_quota_error()]),
        "key-2": FakeTavilyClient("key-2", [_quota_error()]),
    }

    def factory(api_key: str):
        return fakes[api_key]

    with patch.object(search_client_module, "AsyncTavilyClient", side_effect=factory):
        client = SearchClient()
        result = await client.search("AAPL news")

    assert result == ""
    assert fakes["key-1"].calls == ["key-1"]
    assert fakes["key-2"].calls == ["key-2"]


async def test_search_does_not_rotate_on_non_quota_error():
    settings.tavily_api_keys = "key-1,key-2"
    fakes = {
        "key-1": FakeTavilyClient("key-1", [Exception("network timeout")]),
        "key-2": FakeTavilyClient("key-2", [{"results": []}]),
    }

    def factory(api_key: str):
        return fakes[api_key]

    with patch.object(search_client_module, "AsyncTavilyClient", side_effect=factory):
        client = SearchClient()
        result = await client.search("AAPL news")

    # Non-quota errors should NOT trigger key rotation — only key-1 is ever tried.
    assert result == ""
    assert fakes["key-1"].calls == ["key-1"]
    assert fakes["key-2"].calls == []


async def test_search_succeeds_on_first_key_without_rotating():
    settings.tavily_api_keys = "key-1,key-2"
    fakes = {
        "key-1": FakeTavilyClient("key-1", [{"results": [{"title": "fresh", "url": "u", "content": "c", "score": 1.0, "published_date": "2026-09-26"}]}]),
        "key-2": FakeTavilyClient("key-2", []),
    }

    def factory(api_key: str):
        return fakes[api_key]

    with patch.object(search_client_module, "AsyncTavilyClient", side_effect=factory):
        client = SearchClient()
        result = await client.search("AAPL news")

    assert "fresh" in result
    assert fakes["key-2"].calls == []


def test_client_unavailable_when_search_disabled(monkeypatch):
    monkeypatch.setattr(key_pool_module, "_pool", None)
    settings.search_enabled = False
    settings.tavily_api_keys = "key-1"
    client = SearchClient()
    assert client.is_available() is False
