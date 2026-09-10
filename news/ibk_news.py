from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from ib_insync import IB, Stock

from config import NewsConfig


class _StripTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _clean_headline(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _clean_article(text: str, max_chars: int = 1000) -> str:
    parser = _StripTags()
    parser.feed(text)
    clean = re.sub(r"\s+", " ", html.unescape(parser.get_text())).strip()
    if len(clean) > max_chars:
        return clean[:max_chars] + f"… [truncated at {max_chars} chars]"
    return clean


def _divider(char: str = "═", width: int = 60) -> str:
    return char * width


def _deduplicate(headlines: list) -> list:
    """Remove duplicates caused by multi-provider syndication and repeated articleIds.

    Two passes:
    1. Exact: same articleId (IB sometimes returns revised articles twice).
    2. Fuzzy: same normalized headline across different providers (syndicated content).
    """
    seen_ids: set[str] = set()
    seen_headlines: set[str] = set()
    unique = []
    for article in headlines:
        if article.articleId in seen_ids:
            continue
        norm = re.sub(r"\s+", " ", article.headline.lower()).strip()
        if norm in seen_headlines:
            continue
        seen_ids.add(article.articleId)
        seen_headlines.add(norm)
        unique.append(article)
    return unique


def fetch_news(tickers: list[str], cfg: NewsConfig) -> None:
    ib = IB()
    ib.connect(cfg.ibk_host, cfg.ibk_port, clientId=cfg.ibk_client_id)

    providers = ib.reqNewsProviders()
    provider_codes = "+".join(p.code for p in providers)

    if not provider_codes:
        print("No active API news providers found on this account.")
        ib.disconnect()
        return

    for ticker in tickers:
        contract = Stock(ticker, "SMART", "USD")
        ib.qualifyContracts(contract)

        since = datetime.now(timezone.utc) - timedelta(hours=72)
        start_dt = since.strftime("%Y%m%d %H:%M:%S")

        headlines = ib.reqHistoricalNews(
            contract.conId,
            providerCodes=provider_codes,
            startDateTime=start_dt,
            endDateTime="",
            totalResults=cfg.ibk_news_results,
        )
        headlines = _deduplicate(headlines)

        print(_divider())
        print(f" {ticker}  │  {len(headlines)} articles  │  {provider_codes}")
        print(_divider())

        if not headlines:
            print("  No articles found.\n")
            continue

        for i, article in enumerate(headlines, start=1):
            clean_headline = _clean_headline(article.headline)
            timestamp = str(article.time)[:16]

            print(f"\n[{i}] {timestamp}  ({article.providerCode})")
            print(f"    Headline: {clean_headline}")
            print("    " + _divider("─", 56))

            try:
                news_article = ib.reqNewsArticle(article.providerCode, article.articleId)
                body = _clean_article(news_article.articleText)
            except Exception as exc:
                body = f"[Failed to fetch article: {exc}]"

            for line in body.split(". "):
                line = line.strip()
                if line:
                    print(f"    {line}.")

        print()

    ib.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch IBK news headlines and full text.")
    parser.add_argument(
        "tickers",
        nargs="*",
        default=["AAPL"],
        metavar="TICKER",
        help="One or more ticker symbols (default: AAPL)",
    )
    args = parser.parse_args()

    cfg = NewsConfig()
    print(f"Connecting to IB Gateway at {cfg.ibk_host}:{cfg.ibk_port} (clientId={cfg.ibk_client_id})\n")

    try:
        fetch_news([t.upper() for t in args.tickers], cfg)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
