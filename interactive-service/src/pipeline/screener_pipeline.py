from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from ib_async import IB

from src.config.loader import AppConfig, PacingConfig, ScreenerConfig
from src.external.news_data import fetch_news_catalysts
from src.external.yfinance_data import fetch_yfinance_benchmark_data, fetch_yfinance_data
from src.ib.client import IBClient
from src.ib.contract_details import fetch_all_contract_details, fetch_contract_details
from src.ib.historical import (
    fetch_all_daily_bars,
    fetch_all_premarket_bars,
    fetch_all_prev_session_vwap,
)
from src.ib.market_data import fetch_market_snapshots
from src.ib.scanner import run_scanner_batches
from src.ib.volume_profile import fetch_all_volume_profiles
from src.output.writer import write_output
from src.processing.atr import calculate_atr
from src.processing.enrichment import StockRecord, _compute_beta, build_records
from src.processing.filters import (
    apply_screener_filters,
    filter_symbols_by_atr,
    filter_symbols_by_avg_volume,
    reject_reason,
)

log = logging.getLogger(__name__)

_MAX_TOPUP_ITERATIONS = 3  # initial pass + 2 top-up passes


def _log_data_sources(app_config: AppConfig | None) -> None:
    if not app_config:
        return
    log.info("─" * 72)
    log.info("Data Source Configuration:")
    ib_cfg = app_config.ib_data
    ib_fields = {k.replace("output_", ""): v for k, v in ib_cfg.__dict__.items() if k.startswith("output_")}
    ext_cfg = app_config.external_apis
    ext_fields = {k.replace("output_", ""): v for k, v in ext_cfg.__dict__.items() if k.startswith("output_")}
    for field_name, value in sorted({**ib_fields, **ext_fields}.items()):
        log.info(f"  {field_name:<30}: {value if value is not None else 'disabled'}")
    log.info("─" * 72)


def _log_manifest(all_symbols: List[str], drop_log: dict, passed_records: List[StockRecord]) -> None:
    passed_map = {r.symbol: r for r in passed_records}
    sep = "─" * 72
    log.info(sep)
    log.info("SCREENER MANIFEST  %d scanned → %d passed", len(all_symbols), len(passed_records))
    log.info(sep)
    for sym in all_symbols:
        if sym in passed_map:
            rec = passed_map[sym]
            chg = f"{rec.pre_market_chg_pct:+.2f}%" if rec.pre_market_chg_pct is not None else "n/a"
            atr = f"{rec.atr:.2f}%" if rec.atr is not None else "n/a"
            vol = f"{int(rec.pre_market_volume)}" if rec.pre_market_volume is not None else "n/a"
            log.info("  PASS  %-8s  chg=%-8s  ATR=%-7s  vol=%s", sym, chg, atr, vol)
        else:
            log.info("  DROP  %-8s  %s", sym, drop_log.get(sym, "unknown"))
    log.info(sep)


def _apply_phase1_snapshot_filters(
    contract_infos: dict,
    snapshots: dict,
    screener_config: ScreenerConfig,
) -> Tuple[dict, dict, dict]:
    """
    Filter candidates using only market snapshot data (fast, no historical bars needed).

    Applies:
    - Require a valid price snapshot (prev_close or pre_market_price must exist)
    - price_min: reject if effective price is below threshold
    - pre_market_chg_pct_min: reject if pre-market change % is below threshold

    Volume is intentionally NOT filtered here — the streaming tick undercounts by
    40–50% vs the accurate TRADES bar sum and would incorrectly drop valid stocks.

    Returns (surviving_contract_infos, snapshots_with_price, drop_log).
    """
    drop_log: dict[str, str] = {}

    # Require a valid price snapshot
    snapshots_with_price = {
        sym: snap for sym, snap in snapshots.items()
        if snap.pre_market_price is not None or snap.prev_close is not None
    }
    for sym in contract_infos:
        if sym not in snapshots_with_price:
            drop_log[sym] = "no market price data received within timeout"

    surviving = {sym: info for sym, info in contract_infos.items() if sym in snapshots_with_price}

    # price_min filter
    if screener_config.price_min is not None:
        pre = dict(surviving)
        surviving = {}
        for sym, info in pre.items():
            snap = snapshots_with_price[sym]
            effective_price = snap.pre_market_price or snap.prev_close
            if effective_price is not None and effective_price >= screener_config.price_min:
                surviving[sym] = info
            else:
                drop_log[sym] = (
                    f"price {effective_price:.2f} < min {screener_config.price_min:.2f}"
                    if effective_price is not None
                    else f"price unavailable (min {screener_config.price_min:.2f})"
                )

    # pre_market_chg_pct_min filter
    if screener_config.pre_market_chg_pct_min is not None:
        threshold = screener_config.pre_market_chg_pct_min
        pre = dict(surviving)
        surviving = {}
        for sym, info in pre.items():
            snap = snapshots_with_price[sym]
            chg = snap.pre_market_chg_pct
            if chg is not None and chg >= threshold:
                surviving[sym] = info
            else:
                drop_log[sym] = (
                    f"pre_market_chg_pct {chg:+.2f}% < min {threshold:+.2f}%"
                    if chg is not None
                    else f"pre_market_chg_pct unavailable (min {threshold:+.2f}%)"
                )

    log.info(
        "Phase 1 snapshot filter: %d candidates → %d passed (price_min=%s, chg_pct_min=%s)",
        len(contract_infos), len(surviving),
        screener_config.price_min, screener_config.pre_market_chg_pct_min,
    )
    return surviving, snapshots_with_price, drop_log


async def collect_screener_records(
    ib: IB,
    screener_config: ScreenerConfig,
    pacing: PacingConfig,
    app_config: AppConfig | None = None,
) -> List[StockRecord]:
    """
    Two-phase screener pipeline with top-up:

    Phase 1 (cheap, all N scanner symbols):
      contract details → ETF/sector filter → market snapshots → price/chg% filter

    Phase 2 (expensive, only Phase 1 survivors):
      historical bars → ATR/avg_vol pre-filter → pre-market bars → VWAP
      → volume profiles → build records → external enrichment → final filters

    Top-up: if passing records < number_of_rows, re-runs scanner up to 2 extra times,
    skipping already-processed symbols, to fill the gap.
    """
    start_time = time.monotonic()
    _log_data_sources(app_config)

    log.debug(
        "Scanner config: scan_code=%s instrument=%s location_code=%s "
        "number_of_rows=%s avg_volume_min=%s scan_batches=%s",
        screener_config.scan_code, screener_config.instrument,
        screener_config.location_code, screener_config.number_of_rows,
        screener_config.avg_volume_min, screener_config.scan_batches,
    )

    # ── Helper closures ────────────────────────────────────────────────────────
    def _should_output_ib_data(flag_name: str, source: str | None = None) -> bool:
        if not (app_config and hasattr(app_config.ib_data, flag_name)):
            return False
        val = getattr(app_config.ib_data, flag_name)
        return (val == source) if source else (val is not None)

    def _should_output_external_data(flag_name: str, source: str | None = None) -> bool:
        if not (app_config and hasattr(app_config.external_apis, flag_name)):
            return False
        val = getattr(app_config.external_apis, flag_name)
        return (val == source) if source else (val is not None)

    # ── Pre-loop: benchmark (fetched once, shared across all iterations) ───────
    benchmark_sym = getattr(app_config, "benchmark_symbol", "SPY") if app_config else "SPY"
    bm_prev_close:      float | None = None
    bm_pre_market_price: float | None = None
    bm_chg_pct:         float | None = None

    if app_config and app_config.ib_data.output_benchmark_data == "ibk":
        try:
            bm_info = await fetch_contract_details(ib, benchmark_sym)
            if bm_info:
                bm_snaps = await fetch_market_snapshots(ib, [bm_info.contract], pacing)
                bm_snap  = bm_snaps.get(benchmark_sym)
                if bm_snap:
                    bm_prev_close = bm_snap.prev_close
                    bm_chg_pct    = bm_snap.pre_market_chg_pct
        except Exception as e:
            log.warning("Benchmark fetch failed for %s from IBKR: %s", benchmark_sym, e)
    elif app_config and app_config.ib_data.output_benchmark_data == "yfinance":
        log.info("Fetching benchmark data for %s from yfinance...", benchmark_sym)
        try:
            yf_bm_data = await fetch_yfinance_benchmark_data([benchmark_sym])
            if bm_data := yf_bm_data.get(benchmark_sym):
                bm_prev_close       = bm_data.get("prev_close")
                bm_pre_market_price = bm_data.get("pre_market_price")
                bm_chg_pct          = bm_data.get("pre_market_chg_pct")
        except Exception as e:
            log.warning("Benchmark fetch failed for %s from yfinance: %s", benchmark_sym, e)
    else:
        log.info("Skipping benchmark snapshot (output_benchmark_data not configured)")

    if bm_prev_close is not None:
        log.info("Benchmark %s: close=%.2f  chg=%s%%",
                 benchmark_sym, bm_prev_close or 0.0,
                 f"{bm_chg_pct:+.2f}" if bm_chg_pct is not None else "n/a")

    # Cache for benchmark daily bars (beta=calculated); populated on first Phase 2 call
    _bench_bars_cache: dict[str, list] = {}

    # ── Phase 1: cheap, broad (contract details + snapshots + fast filter) ─────
    async def _phase1_candidates(
        candidate_symbols: list[str],
    ) -> tuple[dict, dict, dict[str, str]]:
        """
        Steps 2–2c + 5 + Phase 1 filter.
        Returns (surviving_contract_infos, snapshots_with_price, drop_log).
        """
        drop_log: dict[str, str] = {}

        # Step 2: contract details
        contract_infos = await fetch_all_contract_details(
            ib, candidate_symbols, delay=pacing.contract_details_delay_seconds
        )
        if not contract_infos:
            log.error("Could not resolve any contract details")
            for sym in candidate_symbols:
                drop_log.setdefault(sym, "contract details unavailable")
            return {}, {}, drop_log

        for sym in candidate_symbols:
            if sym not in contract_infos:
                drop_log[sym] = "contract details unavailable"

        # Step 2b: ETF filter
        if screener_config.exclude_etfs:
            etf_types = {"ETF", "ETN", "ETV"}
            pre = dict(contract_infos)
            contract_infos = {
                sym: info for sym, info in pre.items()
                if info.stock_type.upper() not in etf_types
            }
            for sym, info in pre.items():
                if info.stock_type.upper() in etf_types:
                    drop_log[sym] = f"excluded ETF/ETN (stockType={info.stock_type})"
            if not contract_infos:
                log.warning("All symbols were ETFs/ETNs — no stocks remain")
                return {}, {}, drop_log

        # Step 2c: sector exclusion
        if screener_config.exclude_sectors:
            excluded_lower = {s.lower() for s in screener_config.exclude_sectors}
            pre = dict(contract_infos)
            contract_infos = {
                sym: info for sym, info in pre.items()
                if info.sector.lower() not in excluded_lower
            }
            for sym, info in pre.items():
                if info.sector.lower() in excluded_lower:
                    drop_log[sym] = f"sector '{info.sector}' is excluded"
            if not contract_infos:
                log.warning("All symbols excluded by sector filter")
                return {}, {}, drop_log

        # Step 5: market snapshots (batched — all symbols share the 10s wait)
        snapshots: dict = {}
        if app_config and app_config.ib_data.fetch_market_snapshot:
            p1_contracts = [info.contract for info in contract_infos.values()]
            log.info("Phase 1: fetching market snapshots for %d symbols...", len(p1_contracts))
            snapshots = await fetch_market_snapshots(ib, p1_contracts, pacing)
            log.info("Phase 1: snapshots received for %d / %d symbols",
                     len(snapshots), len(p1_contracts))
        else:
            log.info("Skipping market snapshots (fetch_market_snapshot=False)")

        # Phase 1 filter: price_min + pre_market_chg_pct_min (snapshot data only)
        surviving, snapshots_with_price, filter_drops = _apply_phase1_snapshot_filters(
            contract_infos, snapshots, screener_config
        )
        drop_log.update(filter_drops)

        return surviving, snapshots_with_price, drop_log

    # ── Phase 2: expensive, survivors only (historical bars + all enrichment) ──
    async def _phase2_enrich(
        contract_infos: dict,
        snapshots_with_price: dict,
    ) -> tuple[list[StockRecord], dict[str, str]]:
        """
        Steps 3–13 for Phase 1 survivors only.
        Receives pre-fetched contract_infos and snapshots_with_price — does NOT re-fetch them.
        Returns (passing_records, drop_log).
        """
        batch_drop_log: dict[str, str] = {}
        surviving_symbols = list(contract_infos.keys())
        contracts = [info.contract for info in contract_infos.values()]

        # Step 3: historical daily bars
        bars_map: dict = {}
        if app_config and app_config.ib_data.fetch_daily_bars:
            duration = app_config.ib_data.daily_bars_duration
            contracts_for_bars = list(contracts)

            if app_config.ib_data.output_beta == "calculated":
                if benchmark_sym not in _bench_bars_cache:
                    try:
                        bm_info = await fetch_contract_details(ib, benchmark_sym)
                        if bm_info:
                            contracts_for_bars.append(bm_info.contract)
                            log.info("Fetching daily bars for benchmark %s (beta calc)", benchmark_sym)
                    except Exception as e:
                        log.warning("Could not get benchmark contract for daily bars: %s", e)

            if duration != "20 D":
                log.info(
                    "Fetching %s of daily bars for %d symbols — ~%d min at current pacing",
                    duration, len(contracts_for_bars),
                    max(1, int(len(contracts_for_bars) * pacing.historical_delay_seconds / 60)),
                )
            bars_map = await fetch_all_daily_bars(ib, contracts_for_bars, pacing, duration=duration)

            if benchmark_sym in bars_map:
                _bench_bars_cache[benchmark_sym] = bars_map[benchmark_sym]
            elif benchmark_sym in _bench_bars_cache:
                bars_map[benchmark_sym] = _bench_bars_cache[benchmark_sym]
        else:
            log.info("Skipping historical daily bars (fetch_daily_bars=False)")

        # Step 4: ATR pre-filter
        atr_map: dict[str, float | None] = {}
        if app_config and app_config.ib_data.output_atr == "ibk":
            log.info("Pre-filtering by ATR (source: ibk)...")
            atr_period = app_config.ib_data.atr_period
            atr_map = {
                sym: calculate_atr(bars_map[sym], atr_period, symbol=sym)
                if sym in bars_map else None
                for sym in contract_infos
            }
            surviving_symbols = filter_symbols_by_atr(
                surviving_symbols, atr_map, screener_config.atr_min, bars_map=bars_map,
            )
            surviving_set = set(surviving_symbols)
            for sym in contract_infos:
                if sym not in batch_drop_log and sym not in surviving_set:
                    if sym not in bars_map:
                        batch_drop_log[sym] = "historical bars unavailable"
                    elif atr_map.get(sym) is None:
                        batch_drop_log[sym] = f"ATR unavailable (need ≥{atr_period + 1} bars)"
                    else:
                        batch_drop_log[sym] = f"ATR {atr_map[sym]:.2f}% < min {screener_config.atr_min}%"
        else:
            log.info("Skipping ATR pre-filter (source: %s)",
                     app_config.ib_data.output_atr if app_config else "N/A")

        # Step 4b: avg_volume_min pre-filter
        # When source is "yfinance" (yfinance), skip the bars-based pre-filter — IB's
        # RTH-only bar volumes undercount vs yfinance total-session volume and would
        # incorrectly drop stocks. The final Step 13 filter applies avg_volume_min
        # against rec.avg_daily_volume_20d which yfinance populates with total volume.
        avg_vol_source = getattr(getattr(app_config, "ib_data", None), "output_avg_daily_volume_20d", "ibk")
        if avg_vol_source == "yfinance":
            log.info(
                "Skipping bars-based avg_volume pre-filter (source: finhub) — "
                "will apply after yfinance enrichment using total-session volume"
            )
        else:
            pre_avg_vol = surviving_symbols
            surviving_symbols = filter_symbols_by_avg_volume(
                surviving_symbols, bars_map, screener_config.avg_volume_min,
            )
            surviving_set = set(surviving_symbols)
            for sym in pre_avg_vol:
                if sym not in batch_drop_log and sym not in surviving_set:
                    avg_vol = (
                        sum(b.volume for b in bars_map[sym][-20:]) / len(bars_map[sym][-20:])
                        if bars_map.get(sym) else None
                    )
                    batch_drop_log[sym] = (
                        f"avg_daily_volume {avg_vol:.0f} < min {screener_config.avg_volume_min:.0f}"
                        if avg_vol is not None else "avg_daily_volume unavailable"
                    )

        surviving_contracts = [
            contract_infos[s].contract for s in surviving_symbols if s in contract_infos
        ]
        if not surviving_contracts:
            log.warning("All Phase 2 symbols filtered out by ATR/avg-volume thresholds")
            return [], batch_drop_log

        # Step 6: pre-market 1-min bars
        premarket_map: dict = {}
        if app_config and app_config.ib_data.fetch_pre_market_bars:
            log.info("Fetching pre-market 1-min bars for %d symbols...", len(surviving_contracts))
            premarket_map = await fetch_all_premarket_bars(ib, surviving_contracts, pacing)
        else:
            log.info("Skipping pre-market 1-min bars (fetch_pre_market_bars=False)")

        # Step 7: previous session VWAP
        vwap_map: dict = {}
        if app_config and app_config.ib_data.fetch_prev_session_vwap:
            log.info("Fetching previous-session VWAP for %d symbols...", len(surviving_contracts))
            vwap_map = await fetch_all_prev_session_vwap(ib, surviving_contracts, pacing)
        else:
            log.info("Skipping previous-session VWAP (fetch_prev_session_vwap=False)")

        # Step 9: volume profiles
        vp_map: dict = {}
        if app_config and app_config.ib_data.fetch_volume_profile:
            log.info("Fetching volume profiles for %d symbols...", len(surviving_contracts))
            vp_map = await fetch_all_volume_profiles(
                ib, surviving_contracts, pacing,
                lookback_sessions=app_config.ib_data.volume_profile_sessions,
            )
        else:
            log.info("Skipping volume profiles (fetch_volume_profile=False)")

        # Step 10: assemble records
        # snapshots_with_price already contains only symbols with valid price data
        surviving_infos = {
            s: contract_infos[s]
            for s in surviving_symbols
            if s in contract_infos and s in snapshots_with_price
        }
        log.info("Symbols with valid price data after Phase 2 pre-filters: %d / %d",
                 len(surviving_infos), len(surviving_symbols))

        if not surviving_infos:
            log.error("No symbols with valid price data — check IB connection")
            return [], batch_drop_log

        atr_map_surviving = {sym: atr_map[sym] for sym in surviving_infos if sym in atr_map}
        build_kwargs: dict = {"atr_map": atr_map_surviving}
        if app_config:
            if app_config.ib_data.output_atr is not None:
                build_kwargs["atr_period"] = app_config.ib_data.atr_period
            if app_config.ib_data.output_ema is not None:
                build_kwargs["ema_periods"] = app_config.ib_data.ema_periods
            if app_config.ib_data.output_rsi is not None:
                build_kwargs["rsi_period"] = app_config.ib_data.rsi_period

        # snapshots_with_price is passed as both snapshots and snapshots_with_price
        # since all entries already have valid price data (guaranteed by Phase 1 filter)
        records_all = build_records(
            surviving_infos,
            snapshots_with_price,
            bars_map,
            app_config=app_config,
            **build_kwargs,
        )
        log.info("Built %d records from %d surviving symbols", len(records_all), len(surviving_infos))

        # Step 11: patch records with pre-market bars, VWAP, benchmark, VP
        if app_config and _should_output_ib_data("output_vp_poc", source="yfinance"):
            log.warning("Volume Profile from yfinance is not supported and will be null.")

        for rec in records_all:
            pm = premarket_map.get(rec.symbol)
            if pm:
                if _should_output_ib_data("output_pre_market_high"):
                    rec.pre_market_high = pm.pre_market_high
                else:
                    rec.pre_market_high = None
                if _should_output_ib_data("output_pre_market_low"):
                    rec.pre_market_low = pm.pre_market_low
                else:
                    rec.pre_market_low = None
                if _should_output_ib_data("output_rvol_pre_market"):
                    rec.rvol_pre_market = pm.rvol_pre_market
                else:
                    rec.rvol_pre_market = None
                if (pm.pre_market_volume is not None
                        and _should_output_ib_data("output_pre_market_volume", source="ibk")):
                    rec.pre_market_volume = pm.pre_market_volume
            else:
                if _should_output_ib_data("output_pre_market_high"):
                    rec.pre_market_high = None
                if _should_output_ib_data("output_pre_market_low"):
                    rec.pre_market_low = None
                if _should_output_ib_data("output_rvol_pre_market"):
                    rec.rvol_pre_market = None

            if _should_output_ib_data("output_vwap_prev_session", source="ibk"):
                rec.vwap_prev_session = vwap_map.get(rec.symbol)
            else:
                rec.vwap_prev_session = None

            if _should_output_ib_data("output_benchmark_data"):
                rec.benchmark_symbol = benchmark_sym
                rec.benchmark_prev_close = bm_prev_close if _should_output_ib_data("output_benchmark_prev_close") else None
                rec.benchmark_pre_market_price = bm_pre_market_price
                rec.benchmark_pre_market_chg_pct = bm_chg_pct if _should_output_ib_data("output_benchmark_pre_market_chg_pct") else None
            else:
                rec.benchmark_symbol = None
                rec.benchmark_prev_close = None
                rec.benchmark_pre_market_price = None
                rec.benchmark_pre_market_chg_pct = None

            vp = vp_map.get(rec.symbol)
            rec.vp_lookback_sessions = vp.lookback_sessions if vp else None
            rec.vp_poc = (vp.poc if vp else None) if _should_output_ib_data("output_vp_poc", source="ibk") else None
            rec.vp_vah = (vp.vah if vp else None) if _should_output_ib_data("output_vp_vah", source="ibk") else None
            rec.vp_val = (vp.val if vp else None) if _should_output_ib_data("output_vp_val", source="ibk") else None

            if _should_output_ib_data("output_beta", source="calculated"):
                stock_bars = bars_map.get(rec.symbol)
                bench_bars = bars_map.get(benchmark_sym)
                rec.beta = _compute_beta(stock_bars, bench_bars) if (stock_bars and bench_bars) else None

        # Step 12: external enrichment (yfinance + FMP)
        surviving_syms = [rec.symbol for rec in records_all]
        ext_cfg = getattr(app_config, "external_apis", None) if app_config else None
        ib_data_cfg = getattr(app_config, "ib_data", None) if app_config else None

        yf_data: dict = {}
        if app_config:
            ib_finhub = [
                "output_shares_outstanding", "output_market_cap", "output_prev_close",
                "output_fifty_two_week_high", "output_fifty_two_week_low", "output_beta",
                "output_prev_day_high", "output_prev_day_low", "output_prev_day_open",
                "output_avg_daily_volume_20d", "output_atr", "output_ema", "output_rsi",
                "output_pre_market_high", "output_pre_market_low", "output_rvol_pre_market",
                "output_vwap_prev_session",
            ]
            ext_finhub = [
                "output_float_pct", "output_next_earnings_date",
                "output_short_float_pct", "output_short_ratio", "output_institutional_holding_pct",
            ]
            if (any(_should_output_ib_data(f, "yfinance") for f in ib_finhub) or
                    any(_should_output_external_data(f, "yfinance") for f in ext_finhub)):
                log.info("Fetching external data (yfinance) for %d symbols...", len(surviving_syms))
                rvol_lookback = getattr(ib_data_cfg, "pre_market_rvol_lookback", 5) if ib_data_cfg else 5
                yf_data = await fetch_yfinance_data(surviving_syms, rvol_lookback_days=min(rvol_lookback, 5))
            else:
                log.info("Skipping yfinance fetch (no fields configured for 'finhub')")

        news_data: dict = {}
        fmp_key = getattr(ext_cfg, "fmp_api_key", "") if ext_cfg else ""
        max_headlines = getattr(ext_cfg, "news_max_headlines", 3) if ext_cfg else 3
        if fmp_key and max_headlines > 0 and _should_output_external_data("output_news_catalysts", source="yfinance"):
            log.info("Fetching news catalysts via FMP for %d symbols...", len(surviving_syms))
            news_data = await fetch_news_catalysts(surviving_syms, fmp_key, max_headlines)
        else:
            log.info("Skipping news fetch (API key/flag not set or output disabled)")

        finnhub_volume: dict = {}
        finnhub_key = getattr(ext_cfg, "finnhub_api_key", "") if ext_cfg else ""
        if finnhub_key and ib_data_cfg and ib_data_cfg.output_pre_market_volume == "finnhub":
            from src.external.finnhub_data import fetch_finnhub_premarket_volume
            log.info("Fetching pre-market volume from Finnhub for %d symbols...", len(surviving_syms))
            finnhub_volume = await fetch_finnhub_premarket_volume(surviving_syms, finnhub_key)
        elif ib_data_cfg and ib_data_cfg.output_pre_market_volume == "finnhub":
            log.warning("output_pre_market_volume=finnhub but finnhub_api_key is not set — falling back to IB volume")

        for rec in records_all:
            if yf := yf_data.get(rec.symbol):
                if _should_output_external_data("output_next_earnings_date"):
                    rec.next_earnings_date = yf.get("next_earnings_date")
                else:
                    rec.next_earnings_date = None
                if _should_output_external_data("output_short_float_pct"):
                    rec.short_float_pct = yf.get("short_float_pct")
                else:
                    rec.short_float_pct = None
                if _should_output_external_data("output_short_ratio"):
                    rec.short_ratio = yf.get("short_ratio")
                else:
                    rec.short_ratio = None
                if _should_output_external_data("output_institutional_holding_pct"):
                    rec.institutional_holding_pct = yf.get("institutional_holding_pct")
                else:
                    rec.institutional_holding_pct = None

                if ib_data_cfg:
                    if ib_data_cfg.output_shares_outstanding != "ibk" and ib_data_cfg.output_shares_outstanding is not None:
                        rec.shares_outstanding = yf.get("shares_outstanding")
                    elif ib_data_cfg.output_shares_outstanding is None:
                        rec.shares_outstanding = None
                    if ib_data_cfg.output_market_cap != "ibk" and ib_data_cfg.output_market_cap is not None:
                        rec.market_cap_usd = yf.get("market_cap_usd")
                    elif ib_data_cfg.output_market_cap is None:
                        rec.market_cap_usd = None
                    if ib_data_cfg.output_prev_close != "ibk" and ib_data_cfg.output_prev_close is not None:
                        rec.price = yf.get("prev_close")
                    elif ib_data_cfg.output_prev_close is None:
                        rec.price = None
                    if ib_data_cfg.output_fifty_two_week_high != "ibk" and ib_data_cfg.output_fifty_two_week_high is not None:
                        rec.fifty_two_week_high = yf.get("fifty_two_week_high")
                    elif ib_data_cfg.output_fifty_two_week_high is None:
                        rec.fifty_two_week_high = None
                    if ib_data_cfg.output_fifty_two_week_low != "ibk" and ib_data_cfg.output_fifty_two_week_low is not None:
                        rec.fifty_two_week_low = yf.get("fifty_two_week_low")
                    elif ib_data_cfg.output_fifty_two_week_low is None:
                        rec.fifty_two_week_low = None
                    if ib_data_cfg.output_beta == "yfinance":
                        rec.beta = yf.get("beta")
                    elif ib_data_cfg.output_beta is None:
                        rec.beta = None
                    if ib_data_cfg.output_pre_market_high == "yfinance":
                        rec.pre_market_high = yf.get("pre_market_high")
                    if ib_data_cfg.output_pre_market_low == "yfinance":
                        rec.pre_market_low = yf.get("pre_market_low")
                    if ib_data_cfg.output_rvol_pre_market == "yfinance":
                        rec.rvol_pre_market = yf.get("rvol_pre_market")
                    if ib_data_cfg.output_vwap_prev_session == "yfinance":
                        rec.vwap_prev_session = yf.get("vwap_prev_session")
                    if ib_data_cfg.output_pre_market_volume == "yfinance":
                        yf_pmv = yf.get("pre_market_volume")
                        if yf_pmv is not None:
                            rec.pre_market_volume = yf_pmv

                if _should_output_external_data("output_float_pct", source="yfinance"):
                    raw_float = yf.get("float_shares")
                    rec.float_pct = (
                        (raw_float / rec.shares_outstanding) * 100
                        if raw_float is not None and rec.shares_outstanding and rec.shares_outstanding > 0
                        else None
                    )
                else:
                    rec.float_pct = None

                history_df = yf.get("history")
                if history_df is not None and not history_df.empty and ib_data_cfg:
                    history_df = history_df.dropna(subset=['High', 'Low', 'Close', 'Open'])
                    if len(history_df) >= 2:
                        if ib_data_cfg.output_prev_day_high == "yfinance":
                            rec.prev_day_high = history_df['High'].iloc[-2]
                        if ib_data_cfg.output_prev_day_low == "yfinance":
                            rec.prev_day_low = history_df['Low'].iloc[-2]
                        if ib_data_cfg.output_prev_day_open == "yfinance":
                            rec.prev_day_open = history_df['Open'].iloc[-2]
                    if ib_data_cfg.output_avg_daily_volume_20d == "yfinance":
                        rec.avg_daily_volume_20d = history_df['Volume'].tail(20).mean()
                    if ib_data_cfg.output_atr == "yfinance":
                        atr_period = app_config.ib_data.atr_period if app_config else 14
                        if len(history_df) >= atr_period + 1:
                            hl = history_df['High'] - history_df['Low']
                            hc = (history_df['High'] - history_df['Close'].shift()).abs()
                            lc = (history_df['Low'] - history_df['Close'].shift()).abs()
                            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
                            atr_s = tr.ewm(com=atr_period - 1, min_periods=atr_period, adjust=False).mean()
                            atr_v = atr_s.iloc[-1]
                            last_close = history_df['Close'].iloc[-1]
                            if pd.notna(atr_v) and last_close > 0:
                                rec.atr = round(float(atr_v) / last_close * 100, 2)
                    if ib_data_cfg.output_ema == "yfinance":
                        for p in (app_config.ib_data.ema_periods if app_config else []):
                            if len(history_df) >= p:
                                rec.emas[p] = round(
                                    history_df['Close'].ewm(span=p, adjust=False).mean().iloc[-1], 4
                                )
                    if ib_data_cfg.output_rsi == "yfinance":
                        rsi_period = app_config.ib_data.rsi_period if app_config else 14
                        if len(history_df) > rsi_period:
                            delta = history_df['Close'].diff(1)
                            gain = delta.where(delta > 0, 0)
                            loss = -delta.where(delta < 0, 0)
                            avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
                            avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
                            rs = avg_gain / avg_loss
                            if not rs.empty:
                                rec.rsi_14 = round((100 - (100 / (1 + rs))).iloc[-1], 2)
            else:
                if _should_output_external_data("output_float_pct"):
                    rec.float_pct = None
                if _should_output_external_data("output_next_earnings_date"):
                    rec.next_earnings_date = None
                if _should_output_external_data("output_short_float_pct"):
                    rec.short_float_pct = None
                if _should_output_external_data("output_short_ratio"):
                    rec.short_ratio = None
                if _should_output_external_data("output_institutional_holding_pct"):
                    rec.institutional_holding_pct = None
                if ib_data_cfg:
                    if ib_data_cfg.output_shares_outstanding != "ibk" and ib_data_cfg.output_shares_outstanding is not None:
                        rec.shares_outstanding = None
                    if ib_data_cfg.output_market_cap != "ibk" and ib_data_cfg.output_market_cap is not None:
                        rec.market_cap_usd = None
                    if ib_data_cfg.output_prev_close != "ibk" and ib_data_cfg.output_prev_close is not None:
                        rec.price = None
                    if ib_data_cfg.output_fifty_two_week_high != "ibk" and ib_data_cfg.output_fifty_two_week_high is not None:
                        rec.fifty_two_week_high = None
                    if ib_data_cfg.output_fifty_two_week_low != "ibk" and ib_data_cfg.output_fifty_two_week_low is not None:
                        rec.fifty_two_week_low = None
                    if ib_data_cfg.output_beta == "yfinance":
                        rec.beta = None

            if _should_output_external_data("output_news_catalysts", source="yfinance"):
                rec.news_catalysts = news_data.get(rec.symbol, [])
            else:
                rec.news_catalysts = []

        # Step 12a: apply Finnhub pre-market volume
        if finnhub_volume:
            for rec in records_all:
                vol = finnhub_volume.get(rec.symbol)
                if vol is not None:
                    rec.pre_market_volume = vol

        # Step 12b: post-enrichment calculations
        if (app_config and app_config.ib_data.output_market_cap is not None
                and app_config.ib_data.output_avg_daily_volume_20d is not None):
            for rec in records_all:
                if rec.market_cap_usd and rec.avg_daily_volume_20d and rec.avg_daily_volume_20d > 0:
                    rec.mc_vol_ratio = round(rec.market_cap_usd / rec.avg_daily_volume_20d, 2)

        # Step 13: client-side filters
        records_after_std = apply_screener_filters(records_all, screener_config)
        log.info("Standard screener filters: %d → %d", len(records_all), len(records_after_std))

        passing_records = []
        if screener_config.atr_min is not None:
            for rec in records_after_std:
                if rec.atr is not None and rec.atr >= screener_config.atr_min:
                    passing_records.append(rec)
                else:
                    batch_drop_log.setdefault(rec.symbol, (
                        f"ATR {rec.atr:.2f}% < min {screener_config.atr_min}%"
                        if rec.atr is not None
                        else f"ATR unavailable (source: {app_config.ib_data.output_atr if app_config else 'N/A'})"
                    ))
            log.info("ATR filter: %d → %d", len(records_after_std), len(passing_records))
        else:
            passing_records = records_after_std

        passed_syms = {r.symbol for r in passing_records}
        for rec in records_all:
            if rec.symbol not in passed_syms:
                batch_drop_log.setdefault(rec.symbol, reject_reason(rec, screener_config) or "client-side filter")

        log.info(
            "Phase 2 summary: %d candidates → %d historical → %d ATR/vol pass"
            " → %d snapshots → %d records → %d after filters",
            len(list(contract_infos.keys())), len(bars_map),
            len(surviving_symbols), len(snapshots_with_price),
            len(records_all), len(passing_records),
        )
        return passing_records, batch_drop_log

    # ── Orchestration loop: initial pass + up to 2 top-up passes ─────────────
    target = screener_config.number_of_rows
    seen: set[str] = set()
    all_records: list[StockRecord] = []
    all_drop_log: dict[str, str] = {}
    all_scanner_symbols: list[str] = []

    for iteration in range(_MAX_TOPUP_ITERATIONS):
        if iteration > 0:
            if len(all_records) >= target:
                log.info(
                    "Top-up: target of %d records met (%d passing) — stopping",
                    target, len(all_records),
                )
                break
            log.info(
                "Top-up iteration %d/%d: %d/%d records passing — fetching more candidates",
                iteration, _MAX_TOPUP_ITERATIONS - 1, len(all_records), target,
            )

        rows_to_request = min((iteration + 1) * target, 50)
        scan_cfg = dataclasses.replace(screener_config, number_of_rows=rows_to_request)
        raw_syms = await run_scanner_batches(ib, scan_cfg)
        await asyncio.sleep(8.0)

        new_syms = [s for s in raw_syms if s not in seen]
        seen.update(raw_syms)
        all_scanner_symbols.extend(new_syms)

        if not new_syms:
            if iteration == 0:
                log.warning("Scanner returned no symbols — check your scan_code and filters")
            else:
                log.info("Top-up %d: no new symbols from scanner — stopping", iteration)
            break

        log.info(
            "%s: %d new symbol(s) to process%s",
            "Initial scan" if iteration == 0 else f"Top-up {iteration}",
            len(new_syms),
            f" ({len(seen) - len(new_syms)} already seen)" if iteration > 0 else "",
        )

        # Phase 1: cheap — contract details + snapshots + fast filter
        p1_infos, p1_snaps, p1_drops = await _phase1_candidates(new_syms)
        all_drop_log.update(p1_drops)

        if not p1_infos:
            log.info("No symbols survived Phase 1 filter for this iteration")
            continue

        # Phase 2: expensive — only for Phase 1 survivors
        batch_records, p2_drops = await _phase2_enrich(p1_infos, p1_snaps)
        all_records.extend(batch_records)
        all_drop_log.update(p2_drops)

    if not all_scanner_symbols:
        _log_manifest([], {}, [])
        return []

    _log_manifest(all_scanner_symbols, all_drop_log, all_records)

    duration = time.monotonic() - start_time
    log.info("Screener data collection finished in %.2f minutes", duration / 60)
    log.info(
        "Total: %d scanner symbols across all iterations → %d passing records",
        len(all_scanner_symbols), len(all_records),
    )

    return all_records


async def run_screener_pipeline(
    app_config: AppConfig,
    screener_config: ScreenerConfig,
    dry_run: bool = False,
) -> Path:
    """Full screener pipeline: scanner → 2-phase enrichment → write output."""
    async with IBClient(app_config.ib_gateway) as ib:
        records = await collect_screener_records(
            ib, screener_config, app_config.pacing, app_config
        )

    if not records:
        log.warning("No records passed all filters")
        return write_output([], app_config)

    if dry_run:
        log.info("[dry-run] Would write %d records to %s",
                 len(records), app_config.output.directory)
        return Path(app_config.output.directory) / "dry_run.json"

    return write_output(records, app_config, max_stocks=app_config.max_number_of_stocks)
