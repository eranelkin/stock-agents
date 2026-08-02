"""Merged pipeline: runs screener and watchlist in one IB session, merges results."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from src.config.loader import AppConfig, ScreenerConfig, WatchlistEntry
from src.ib.client import IBClient
from src.output.writer import write_output
from src.pipeline.screener_pipeline import collect_screener_records
from src.pipeline.watchlist_pipeline import collect_watchlist_records
from src.processing.enrichment import StockRecord

log = logging.getLogger(__name__)


async def run_merged_pipeline(
    app_config: AppConfig,
    screener_config: ScreenerConfig,
    watchlist: List[WatchlistEntry],
    dry_run: bool = False,
) -> Path:
    """
    Run screener and watchlist pipelines in a single IB session, deduplicate by symbol,
    sort by pre_market_chg_pct, and write one YAML file.

    Screener records take priority in deduplication (they carry ATR + sector filters).
    Watchlist adds any symbols not found by the scanner.
    """
    log.info("Starting merged pipeline (screener + watchlist)...")

    async with IBClient(app_config.ib_gateway) as ib:
        screener_records = await collect_screener_records(ib, screener_config, app_config.pacing, app_config)
        watchlist_records = await collect_watchlist_records(ib, watchlist, app_config.pacing, app_config)

    log.info(
        "Merged: %d screener records + %d watchlist records before dedup",
        len(screener_records), len(watchlist_records),
    )

    # Screener records first — they carry the quality filters.
    # Watchlist adds symbols not discovered by the scanner.
    seen: set[str] = set()
    combined: List[StockRecord] = []
    for rec in screener_records:
        if rec.symbol not in seen:
            combined.append(rec)
            seen.add(rec.symbol)
    for rec in watchlist_records:
        if rec.symbol not in seen:
            combined.append(rec)
            seen.add(rec.symbol)

    log.info("Merged %d unique records total", len(combined))

    if dry_run:
        log.info("[dry-run] Would write %d records to %s", len(combined), app_config.output.directory)
        return Path(app_config.output.directory) / "dry_run.yaml"

    return write_output(combined, app_config, max_stocks=app_config.max_number_of_stocks)
