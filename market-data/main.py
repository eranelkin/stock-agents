#!/usr/bin/env python3
"""
market-data — Fetch ETF, S&P 500, VIX, and sentiment data via Alpha Vantage.

Usage:
  python main.py                        # fetch all symbols and save output
  python main.py --dry-run              # validate config, skip API calls
  python main.py --etf-list ./ETF_list.json  # custom ETF list path
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click

ROOT = Path(__file__).parent
DEFAULT_ETF_LIST = ROOT / "ETF_list.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"

# Extra symbols always fetched in addition to the ETF list
EXTRA_SYMBOLS = [
    {"symbol": "SPY",  "name": "SPDR S&P 500 ETF Trust",  "sector": "Index",      "type": "sp500_proxy"},
    {"symbol": "QQQ",  "name": "Invesco QQQ Trust",         "sector": "Index",      "type": "nasdaq_proxy"},
    {"symbol": "VIX",  "name": "CBOE Volatility Index",     "sector": "Volatility", "type": "volatility"},
]


def _setup_logging(run_ts: str) -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"market_data_{run_ts}.log"

    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    file_h = logging.FileHandler(log_path, encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_h)

    logging.getLogger(__name__).info("Log file: %s", log_path)


def _load_etf_list(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    sectors = data.get("sectors", [])
    symbols: list[dict[str, str]] = []
    for item in sectors:
        sym = item.get("etf_symbol", "").strip()
        if sym:
            symbols.append({
                "symbol": sym,
                "name": item.get("etf_name", ""),
                "sector": item.get("name", ""),
                "type": "sector_etf",
            })
    return symbols


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--etf-list",
    type=click.Path(exists=True, path_type=Path),
    default=str(DEFAULT_ETF_LIST),
    show_default=True,
    help="Path to ETF_list.json",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=str(DEFAULT_OUTPUT_DIR),
    show_default=True,
    help="Directory where output JSON files are written.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Load config and ETF list but skip API calls.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    show_default=True,
)
def main(
    etf_list: Path,
    output_dir: Path,
    dry_run: bool,
    log_level: str,
) -> None:
    """Fetch market data for all ETFs, S&P 500, and VIX."""
    run_ts = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    _setup_logging(run_ts)
    log = logging.getLogger(__name__)

    # Import here so logging is configured first
    from config import settings  # noqa: PLC0415
    from fetcher import fetch_all  # noqa: PLC0415

    log.info("=" * 60)
    log.info("Market Data Service — starting run %s", run_ts)
    log.info("=" * 60)

    if not settings.alpha_vantage_api_key:
        log.error(
            "ALPHA_VANTAGE_API_KEY is not set. "
            "Get a free key at https://www.alphavantage.co/support/#api-key"
        )
        sys.exit(1)

    # Load ETF list
    log.info("Loading ETF list from: %s", etf_list)
    etf_symbols = _load_etf_list(etf_list)
    all_symbols = etf_symbols + EXTRA_SYMBOLS

    # Deduplicate by symbol
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for s in all_symbols:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            deduped.append(s)

    # Apply symbol cap (ALPHA_VANTAGE_MAX_SYMBOLS in .env, default 5)
    max_sym = settings.alpha_vantage_max_symbols
    if max_sym > 0 and len(deduped) > max_sym:
        log.info(
            "Symbol cap: ALPHA_VANTAGE_MAX_SYMBOLS=%d — limiting from %d to %d symbols.",
            max_sym, len(deduped), max_sym,
        )
        deduped = deduped[:max_sym]

    log.info("Total symbols to fetch: %d", len(deduped))
    log.info("  (Set ALPHA_VANTAGE_MAX_SYMBOLS=0 in .env to fetch all %d)", len(etf_symbols) + len(EXTRA_SYMBOLS))

    if dry_run:
        log.info("[DRY RUN] Skipping API calls. Config OK.")
        for s in deduped:
            log.info("  Would fetch: %s (%s)", s["symbol"], s["name"])
        return

    if settings.finnhub_api_key:
        log.info("Sentiment source: Finnhub (free, 60 req/min, no daily cap)")
    else:
        log.warning("FINNHUB_API_KEY not set — sentiment will be skipped. Get a free key at https://finnhub.io")

    start = time.monotonic()
    results = asyncio.run(
        fetch_all(deduped, settings.alpha_vantage_api_key, settings.alpha_vantage_rpm, settings.finnhub_api_key)
    )
    elapsed = time.monotonic() - start

    # Build output
    successful = sum(1 for v in results.values() if "error" not in v.get("quote", {}))
    failed = len(results) - successful

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "alpha_vantage",
        "symbols": results,
        "metadata": {
            "total_symbols": len(deduped),
            "successful_quotes": successful,
            "failed_quotes": failed,
            "duration_seconds": round(elapsed, 2),
            "api_rpm_setting": settings.alpha_vantage_rpm,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"market_{run_ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info("=" * 60)
    log.info("Run complete in %.1fs", elapsed)
    log.info("Symbols fetched: %d/%d (failed: %d)", successful, len(deduped), failed)
    log.info("Output written: %s", output_path)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
