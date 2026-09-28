from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time as dtime
from typing import Any
from zoneinfo import ZoneInfo

import yfinance as yf

logger = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")
_PREMARKET_END = dtime(9, 30)

_BULLISH = {
    "bull", "bullish", "buy", "upgrade", "outperform", "surge", "soar", "rally",
    "gain", "gains", "rise", "rises", "rose", "climb", "climbs", "jump", "jumps",
    "beat", "beats", "strong", "strength", "record", "high", "boost", "positive",
    "upside", "opportunity", "growth",
}
_BEARISH = {
    "bear", "bearish", "sell", "downgrade", "underperform", "fall", "falls", "fell",
    "drop", "drops", "dropped", "decline", "declines", "declined", "crash", "slump",
    "plunge", "tumble", "loss", "losses", "miss", "misses", "weak", "weakness",
    "concern", "concerns", "worry", "risk", "risks", "down", "negative", "cut",
}


def _keyword_sentiment(news: list[dict[str, Any]]) -> dict[str, Any]:
    """Score sentiment from yfinance news titles + summaries using keyword counting."""
    bullish = 0
    bearish = 0
    texts: list[str] = []

    for item in news:
        content = item.get("content", {})
        title = (content.get("title") or "").lower()
        summary = (content.get("summary") or "").lower()
        text = f"{title} {summary}"
        texts.append(text)
        words = set(text.split())
        bullish += len(words & _BULLISH)
        bearish += len(words & _BEARISH)

    total = bullish + bearish
    if total == 0:
        score = 0.0
        label = "Neutral"
    else:
        score = round((bullish - bearish) / total, 4)
        if score >= 0.2:
            label = "Bullish"
        elif score <= -0.2:
            label = "Bearish"
        else:
            label = "Neutral"

    return {
        "score": score,
        "label": label,
        "bullish_signals": bullish,
        "bearish_signals": bearish,
        "article_count": len(news),
        "source": "yfinance_keyword",
    }


def _extract_premarket(info: dict[str, Any], ticker: yf.Ticker) -> dict[str, Any]:
    """Return pre-market data using info fields when available, history as fallback."""
    pm_price = info.get("preMarketPrice")
    if pm_price is not None:
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        change = round(pm_price - prev_close, 4) if prev_close else None
        change_pct = round((change / prev_close) * 100, 4) if change and prev_close else None
        return {
            "price": pm_price,
            "change": info.get("preMarketChange", change),
            "change_percent": info.get("preMarketChangePercent", change_pct),
            "volume": info.get("preMarketVolume"),
            "source": "info",
        }

    try:
        hist = ticker.history(period="2d", interval="1m", prepost=True)
        if hist.empty:
            return {"price": None, "change": None, "change_percent": None, "volume": None, "source": "unavailable"}

        now_et = datetime.now(_ET)
        today_et = now_et.date()

        pre = hist[
            (hist.index.date == today_et) &  # type: ignore[attr-defined]
            (hist.index.map(lambda x: x.astimezone(_ET).time()) < _PREMARKET_END)  # type: ignore[attr-defined]
        ]
        if pre.empty:
            yesterday = hist.index[-1].date()
            pre = hist[
                (hist.index.date == yesterday) &  # type: ignore[attr-defined]
                (hist.index.map(lambda x: x.astimezone(_ET).time()) < _PREMARKET_END)  # type: ignore[attr-defined]
            ]

        if pre.empty:
            return {"price": None, "change": None, "change_percent": None, "volume": None, "source": "unavailable"}

        pm_price = float(pre["Close"].iloc[-1])
        pm_volume = int(pre["Volume"].sum())
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        change = round(pm_price - prev_close, 4) if prev_close else None
        change_pct = round((change / prev_close) * 100, 4) if change and prev_close else None

        return {
            "price": pm_price,
            "change": change,
            "change_percent": change_pct,
            "volume": pm_volume if pm_volume > 0 else None,
            "source": "history",
        }

    except Exception as exc:
        logger.warning("Pre-market history fallback failed: %s", exc)
        return {"price": None, "change": None, "change_percent": None, "volume": None, "source": "error"}


async def fetch_quotes_yfinance(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch quotes, pre-market data, and keyword sentiment via yfinance (free, no rate limit)."""
    logger.info("Fetching data for %d symbols via yfinance...", len(symbols))

    loop = asyncio.get_event_loop()

    def _download() -> dict[str, dict[str, Any]]:
        yf_symbols = ["^VIX" if s == "VIX" else s for s in symbols]
        sym_map = {("^VIX" if s == "VIX" else s): s for s in symbols}
        tickers = yf.Tickers(" ".join(yf_symbols))
        result: dict[str, dict[str, Any]] = {}

        for yf_sym, orig_sym in sym_map.items():
            try:
                ticker = tickers.tickers[yf_sym]
                info = ticker.info

                quote = {
                    "price": info.get("regularMarketPrice"),
                    "open": info.get("regularMarketOpen"),
                    "high": info.get("regularMarketDayHigh"),
                    "low": info.get("regularMarketDayLow"),
                    "volume": info.get("regularMarketVolume"),
                    "prev_close": info.get("regularMarketPreviousClose"),
                    "change": info.get("regularMarketChange"),
                    "change_percent": info.get("regularMarketChangePercent"),
                    "market_cap": info.get("marketCap"),
                    "currency": info.get("currency"),
                    "market_state": info.get("marketState"),
                }

                pre_market = _extract_premarket(info, ticker)

                news = ticker.news or []
                sentiment = _keyword_sentiment(news)

                price = quote.get("price") or 0
                chg = quote.get("change_percent") or 0
                pm_price = pre_market.get("price")
                logger.info(
                    "  ✓ %-6s  price=%-8.2f  chg=%+.2f%%  pre=%-8s  sentiment=%-8s (%d articles)",
                    orig_sym, price, chg,
                    f"{pm_price:.2f}" if pm_price else "n/a",
                    sentiment["label"],
                    sentiment["article_count"],
                )

                result[orig_sym] = {"quote": quote, "pre_market": pre_market, "sentiment": sentiment}

            except Exception as exc:
                logger.warning("  ✗ %s  failed: %s", orig_sym, exc)
                result[orig_sym] = {"error": str(exc)}

        return result

    return await loop.run_in_executor(None, _download)


async def fetch_all(
    symbols: list[dict[str, str]],
    api_key: str = "",
    rpm: int = 5,
    finnhub_api_key: str = "",
) -> dict[str, Any]:
    """
    Fetch quotes, pre-market data, and sentiment for all symbols via yfinance (100% free).

    Args:
        symbols: list of dicts with keys: symbol, name, sector, type
        api_key: unused — kept for API compatibility
        rpm: unused — kept for API compatibility
        finnhub_api_key: unused — kept for API compatibility
    """
    sym_list = [s["symbol"] for s in symbols]
    meta_by_symbol = {s["symbol"]: s for s in symbols}

    data_map = await fetch_quotes_yfinance(sym_list)

    result: dict[str, Any] = {}
    for sym in sym_list:
        meta = meta_by_symbol[sym]
        entry = data_map.get(sym, {})
        result[sym] = {
            "symbol": sym,
            "name": meta.get("name", ""),
            "sector": meta.get("sector", ""),
            "type": meta.get("type", "etf"),
            "quote": entry.get("quote", {"error": entry.get("error", "failed")}),
            "pre_market": entry.get("pre_market", {"price": None, "source": "unavailable"}),
            "sentiment": entry.get("sentiment", {"score": None, "label": "Neutral", "article_count": 0}),
        }

    return result
