from __future__ import annotations

import pytest

from ai_service.utils.tavily_key_pool import TavilyKeyPool, get_tavily_key_pool


def test_current_key_returns_first_key():
    pool = TavilyKeyPool(["key-a", "key-b", "key-c"])
    assert pool.current_key() == "key-a"
    assert pool.total_keys == 3
    assert not pool.all_exhausted


def test_current_key_returns_none_when_no_keys_configured():
    pool = TavilyKeyPool([])
    assert pool.current_key() is None
    assert pool.total_keys == 0


async def test_rotate_advances_to_next_live_key():
    pool = TavilyKeyPool(["key-a", "key-b", "key-c"])
    next_key = await pool.mark_exhausted_and_rotate()
    assert next_key == "key-b"
    assert pool.current_key() == "key-b"
    assert not pool.all_exhausted


async def test_rotate_skips_previously_exhausted_keys():
    pool = TavilyKeyPool(["key-a", "key-b", "key-c"])
    await pool.mark_exhausted_and_rotate()  # a -> b
    next_key = await pool.mark_exhausted_and_rotate()  # b -> c
    assert next_key == "key-c"


async def test_rotate_returns_none_once_all_keys_exhausted():
    pool = TavilyKeyPool(["key-a", "key-b"])
    await pool.mark_exhausted_and_rotate()  # a -> b
    next_key = await pool.mark_exhausted_and_rotate()  # b -> nothing left
    assert next_key is None
    assert pool.all_exhausted


async def test_rotate_on_single_key_pool_returns_none():
    pool = TavilyKeyPool(["only-key"])
    next_key = await pool.mark_exhausted_and_rotate()
    assert next_key is None
    assert pool.all_exhausted


async def test_rotate_on_empty_pool_returns_none():
    pool = TavilyKeyPool([])
    next_key = await pool.mark_exhausted_and_rotate()
    assert next_key is None


def test_get_tavily_key_pool_is_a_process_wide_singleton(monkeypatch):
    import ai_service.utils.tavily_key_pool as module

    monkeypatch.setattr(module, "_pool", None)
    first = get_tavily_key_pool()
    second = get_tavily_key_pool()
    assert first is second
