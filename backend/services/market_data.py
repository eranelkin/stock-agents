from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# Yahoo Finance's public (undocumented) chart endpoint — no API key required.
# Same data source used by this project's other candle-fetching pipelines.
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_FETCH_TIMEOUT_SECONDS = 10.0
# Yahoo's anti-bot layer is more likely to block the default httpx UA string
# than a browser-like one.
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


@dataclass(frozen=True)
class Candle:
    timestamp: datetime  # tz-aware, America/New_York
    open: float
    high: float
    low: float
    close: float
    volume: float


async def fetch_1m_candles(symbol: str, trading_date: date) -> list[Candle] | None:
    """Fetch 1-minute OHLC candles for one symbol on one ET trading date.

    Hits Yahoo Finance's chart endpoint directly, bounded to the exact trading
    day via period1/period2 (unix seconds) rather than a relative "range"
    string — we always want one specific historical day, not "however much
    history is available from today". Returns None if Yahoo has no data for
    that date (e.g. it's outside the ~7-day 1m history window) or the request
    fails/times out — callers treat None as the "no_data" scan outcome.
    """
    period1 = int(
        datetime.combine(trading_date, datetime.min.time(), tzinfo=ET)
        .astimezone(timezone.utc)
        .timestamp()
    )
    period2 = int(
        datetime.combine(trading_date + timedelta(days=1), datetime.min.time(), tzinfo=ET)
        .astimezone(timezone.utc)
        .timestamp()
    )

    url = _CHART_URL.format(symbol=symbol)
    params = {"interval": "1m", "period1": period1, "period2": period2}

    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS, headers=_HEADERS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("Yahoo chart fetch failed for %s on %s: %s", symbol, trading_date, exc)
        return None

    result_list = (payload.get("chart") or {}).get("result")
    if not result_list:
        return None

    result = result_list[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: list[Candle] = []
    for i, ts in enumerate(timestamps):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        v = volumes[i] if i < len(volumes) else None

        if None in (o, h, l, c):
            continue  # Yahoo returns nulls for holes (e.g. halted symbol)
        if o == h == l == c:
            continue  # flat candle — Yahoo junk bar

        candles.append(
            Candle(
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET),
                open=float(o),
                high=float(h),
                low=float(l),
                close=float(c),
                volume=float(v) if v is not None else 0.0,
            )
        )

    return candles or None
