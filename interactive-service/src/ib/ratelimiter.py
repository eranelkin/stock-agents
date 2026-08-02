from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

log = logging.getLogger(__name__)


class HistoricalLimiter:
    """≤59 requests per any 10-minute sliding window with optional minimum inter-request gap.

    The min_gap argument to acquire() enforces a floor delay between consecutive
    acquisitions so IB's data farm is not overwhelmed by bursts of simultaneous
    requests (which causes 45s timeouts even within the 59/10-min quota).
    """
    _MAX = 59
    _WINDOW = 600.0

    def __init__(self) -> None:
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._last_acquired: float = 0.0

    async def acquire(self, min_gap: float = 0.0) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] > self._WINDOW:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._MAX:
                    since_last = now - self._last_acquired
                    if since_last >= min_gap:
                        self._timestamps.append(now)
                        self._last_acquired = now
                        return
                    # Window has room but min_gap not satisfied yet — wait the remainder
                    wait = min_gap - since_last + 0.01
                    log.debug("Rate limiter: min-gap wait %.2f s", wait)
                else:
                    wait = self._timestamps[0] + self._WINDOW - now + 0.1
                    log.info(
                        "Historical rate limit: pausing %.1f s (queue: %d/%d)",
                        wait, len(self._timestamps), self._MAX,
                    )
            await asyncio.sleep(wait)


# Singleton instance for all historical data calls to share
limiter = HistoricalLimiter()
