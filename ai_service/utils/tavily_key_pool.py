from __future__ import annotations

import asyncio
import time

from ai_service.config import settings
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


class TavilyKeyPool:
    """Process-wide rotation over multiple Tavily API keys.

    SearchClient instances are created fresh per call site, so rotation state
    (which key is current, which are exhausted) must live here instead —
    otherwise every new SearchClient would retry from the first key.

    An exhausted key isn't dropped forever — it becomes eligible again after
    `cooldown_seconds`, since most quota/rate-limit errors are transient
    (per-minute/per-day caps that clear on their own) rather than a true
    exhausted-until-next-billing-month state. Without this, one rate-limit
    blip permanently disables a key for the life of the process.
    """

    def __init__(self, keys: list[str], cooldown_seconds: float | None = None) -> None:
        self._keys = keys
        self._index = 0
        self._exhausted_at: dict[int, float] = {}  # key index -> monotonic time marked exhausted
        self._cooldown_seconds = (
            cooldown_seconds if cooldown_seconds is not None else settings.tavily_key_cooldown_seconds
        )
        self._lock = asyncio.Lock()

    def _is_exhausted(self, index: int) -> bool:
        """A key counts as exhausted only while still within its cooldown window."""
        marked_at = self._exhausted_at.get(index)
        if marked_at is None:
            return False
        if time.monotonic() - marked_at >= self._cooldown_seconds:
            del self._exhausted_at[index]
            return False
        return True

    def current_key(self) -> str | None:
        if not self._keys or self._index >= len(self._keys):
            return None
        return self._keys[self._index]

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    async def mark_exhausted_and_rotate(self) -> str | None:
        """Mark the current key exhausted and return the next live key, or None if all are exhausted."""
        async with self._lock:
            exhausted_index = self._index
            self._exhausted_at[exhausted_index] = time.monotonic()
            for offset in range(1, len(self._keys) + 1):
                candidate = (exhausted_index + offset) % len(self._keys)
                if not self._is_exhausted(candidate):
                    self._index = candidate
                    logger.warning(
                        "Tavily key %d/%d exhausted — rotating to key %d/%d",
                        exhausted_index + 1,
                        len(self._keys),
                        candidate + 1,
                        len(self._keys),
                    )
                    return self._keys[candidate]
            logger.error(
                "All %d Tavily keys exhausted (each retries automatically after %.0fs)",
                len(self._keys),
                self._cooldown_seconds,
            )
            return None

    @property
    def all_exhausted(self) -> bool:
        return bool(self._keys) and all(self._is_exhausted(i) for i in range(len(self._keys)))


_pool: TavilyKeyPool | None = None


def get_tavily_key_pool() -> TavilyKeyPool:
    """Return the shared, lazily-initialized Tavily key pool for this process."""
    global _pool
    if _pool is None:
        _pool = TavilyKeyPool(settings.tavily_api_key_list)
    return _pool
