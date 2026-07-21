from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from ai_service.utils.logger import get_logger

logger = get_logger(__name__)

# Finnhub WebSocket endpoint
_FINNHUB_WS_URL = "wss://ws.finnhub.io"


@dataclass
class PreMarketQuote:
    """Snapshot of pre-market trading activity for one symbol."""

    price: float | None = None
    change: float | None = None       # absolute change from previous close
    change_pct: float | None = None   # percentage change from previous close
    volume: float | None = None
    timestamp: datetime | None = None


class PreMarketStreamer:
    """Background WebSocket client that maintains a live pre-market quote cache.

    Connects to the Finnhub WebSocket feed on startup, subscribes to requested
    symbols, and accumulates trades into an in-memory cache.  The enricher reads
    from the cache at enrichment time so it always gets the freshest available data.

    Usage:
        streamer = PreMarketStreamer(api_key="...")
        await streamer.start()
        # ... later ...
        streamer.subscribe(["AAPL", "MSFT", "ES=F"])
        quote = streamer.get("AAPL")
        await streamer.stop()
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # symbol → PreMarketQuote (latest trade price + cumulative session volume)
        self._cache: dict[str, PreMarketQuote] = {}
        # prev-close per symbol, used to compute change / change_pct
        self._prev_close: dict[str, float] = {}
        # symbols pending subscription (consumed by the receive loop)
        self._pending_subs: list[str] = []
        self._ws: Any = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background WebSocket receive loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="premarket-streamer")
        logger.info("PreMarketStreamer started")

    async def stop(self) -> None:
        """Gracefully stop the streamer."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        logger.info("PreMarketStreamer stopped")

    def subscribe(self, symbols: list[str]) -> None:
        """Queue symbols for subscription on the next loop iteration."""
        new = [s for s in symbols if s not in self._cache]
        self._pending_subs.extend(new)
        # Pre-populate cache slots so callers can tell the difference between
        # "never subscribed" and "subscribed but no trades yet"
        for s in new:
            self._cache.setdefault(s, PreMarketQuote())

    def get(self, symbol: str) -> PreMarketQuote | None:
        """Return the latest cached quote for a symbol, or None if not subscribed."""
        return self._cache.get(symbol)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Connect and receive messages, reconnecting on transient errors."""
        import websockets  # imported lazily so the module loads without websockets installed

        url = f"{_FINNHUB_WS_URL}?token={self._api_key}"
        backoff = 1.0

        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._ws = ws
                    backoff = 1.0
                    logger.info("Finnhub WebSocket connected")

                    # Send any already-queued subscriptions
                    await self._flush_pending_subs(ws)

                    async for raw in ws:
                        if not self._running:
                            break
                        # Flush any new subscriptions that arrived while we were reading
                        if self._pending_subs:
                            await self._flush_pending_subs(ws)
                        self._handle_message(raw)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.warning(
                    "Finnhub WebSocket disconnected (%s) — reconnecting in %.0fs",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

        self._ws = None

    async def _flush_pending_subs(self, ws: Any) -> None:
        """Send subscribe messages for all pending symbols."""
        while self._pending_subs:
            symbol = self._pending_subs.pop(0)
            msg = json.dumps({"type": "subscribe", "symbol": symbol})
            await ws.send(msg)
            logger.debug("Subscribed to %s on Finnhub", symbol)

    def _handle_message(self, raw: str) -> None:
        """Parse a Finnhub WebSocket message and update the cache."""
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return

        if msg.get("type") != "trade":
            return

        for trade in msg.get("data", []):
            symbol: str = trade.get("s", "")
            price: float | None = trade.get("p")
            volume: float | None = trade.get("v")
            ts_ms: int | None = trade.get("t")

            if not symbol or price is None:
                continue

            existing = self._cache.get(symbol, PreMarketQuote())
            prev_vol = existing.volume or 0.0
            new_vol = prev_vol + (volume or 0.0)

            prev_close = self._prev_close.get(symbol)
            change = round(price - prev_close, 4) if prev_close else None
            change_pct = round((price - prev_close) / prev_close * 100, 4) if prev_close else None

            self._cache[symbol] = PreMarketQuote(
                price=round(price, 4),
                change=change,
                change_pct=change_pct,
                volume=round(new_vol, 0),
                timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) if ts_ms else None,
            )

    def set_prev_close(self, symbol: str, prev_close: float) -> None:
        """Provide the previous close so the streamer can compute change fields."""
        self._prev_close[symbol] = prev_close
        # Recompute change on existing cache entry if we have a price already
        existing = self._cache.get(symbol)
        if existing and existing.price is not None:
            self._cache[symbol] = PreMarketQuote(
                price=existing.price,
                change=round(existing.price - prev_close, 4),
                change_pct=round((existing.price - prev_close) / prev_close * 100, 4),
                volume=existing.volume,
                timestamp=existing.timestamp,
            )


# ---------------------------------------------------------------------------
# Fallback: yfinance snapshot (15-min delayed, no key required)
# ---------------------------------------------------------------------------

async def fetch_premarket_yfinance(symbol: str) -> PreMarketQuote:
    """Fetch a pre-market snapshot via yfinance fast_info (15-min delayed).

    Args:
        symbol: Ticker symbol, e.g. "AAPL".

    Returns:
        PreMarketQuote with available fields populated, others None.
    """
    def _get() -> PreMarketQuote:
        try:
            info = yf.Ticker(symbol).fast_info
            price: float | None = getattr(info, "pre_market_price", None)
            prev_close: float | None = getattr(info, "regular_market_previous_close", None)

            change: float | None = None
            change_pct: float | None = None
            if price is not None and prev_close:
                change = round(price - prev_close, 4)
                change_pct = round((price - prev_close) / prev_close * 100, 4)

            return PreMarketQuote(
                price=round(price, 4) if price is not None else None,
                change=change,
                change_pct=change_pct,
                volume=None,  # yfinance fast_info doesn't expose pre-market volume
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.warning("yfinance pre-market fetch failed for %s: %s", symbol, exc)
            return PreMarketQuote()

    return await asyncio.to_thread(_get)


