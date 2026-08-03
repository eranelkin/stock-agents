from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List

import pandas as pd
from ib_async import IB

from src.config.loader import AppConfig, PacingConfig, WatchlistEntry
from src.external.news_data import fetch_news_catalysts
from src.external.yfinance_data import fetch_yfinance_data
from src.ib.client import IBClient
from src.ib.contract_details import fetch_all_contract_details, fetch_contract_details
from src.ib.historical import (
    fetch_all_daily_bars,
    fetch_all_premarket_bars,
    fetch_all_prev_session_vwap,
)
from src.ib.market_data import fetch_market_snapshots
from src.ib.volume_profile import fetch_all_volume_profiles
from src.output.writer import write_output
from src.processing.enrichment import StockRecord, _compute_beta, build_records

log = logging.getLogger(__name__)


def _log_data_sources(app_config: AppConfig | None) -> None:
    """Log the configured source for each data field."""
    if not app_config:
        return

    log.info("─" * 72)
    log.info("Data Source Configuration:")

    ib_cfg = app_config.ib_data
    ib_fields = {k.replace("output_", ""): v for k, v in ib_cfg.__dict__.items() if k.startswith("output_")}

    ext_cfg = app_config.external_apis
    ext_fields = {k.replace("output_", ""): v for k, v in ext_cfg.__dict__.items() if k.startswith("output_")}

    all_fields = {**ib_fields, **ext_fields}

    for field_name, value in sorted(all_fields.items()):
        source = value if value is not None else "disabled"
        log.info(f"  {field_name:<30}: {source}")

    log.info("─" * 72)


async def collect_watchlist_records(
    ib: IB,
    watchlist: List[WatchlistEntry],
    pacing: PacingConfig,
    app_config: AppConfig | None = None,
) -> List[StockRecord]:
    """
    Core watchlist logic:
      contract details → historical bars → market snapshots
      → pre-market 1-min bars → prev-session VWAP → benchmark
      → volume profiles → build records → patch → external enrichment

    No filters applied — all watchlist symbols always appear (missing fields are null).
    Returns a list of StockRecord; does NOT open a connection or write output.
    Callers own the IB connection.
    """
    start_time = time.monotonic()
    symbols = [entry.symbol for entry in watchlist]
    log.info("Running watchlist pipeline for %d symbols: %s", len(symbols), symbols)
    _log_data_sources(app_config)

    # ── Step 1: contract details ───────────────────────────────────────────────
    contract_infos = await fetch_all_contract_details(
        ib, symbols, delay=pacing.contract_details_delay_seconds
    )
    if not contract_infos:
        log.error("Could not resolve any contract details from watchlist")
        return []

    unresolved = set(symbols) - set(contract_infos.keys())
    if unresolved:
        log.warning("Could not resolve: %s", sorted(unresolved))

    # ── Step 2: historical daily bars ─────────────────────────────────────────
    contracts = [info.contract for info in contract_infos.values()]
    bars_map = {}
    if app_config and app_config.ib_data.fetch_daily_bars:
        duration = app_config.ib_data.daily_bars_duration
        
        contracts_for_bars = list(contracts)
        benchmark_sym = getattr(app_config, "benchmark_symbol", "SPY") if app_config else "SPY"
        if app_config.ib_data.output_beta == "calculated":
            try:
                bm_info = await fetch_contract_details(ib, benchmark_sym)
                if bm_info:
                    contracts_for_bars.append(bm_info.contract)
                    log.info("Will also fetch daily bars for benchmark %s (for beta calculation)", benchmark_sym)
            except Exception as e:
                log.warning("Could not get contract for benchmark %s for daily bars: %s", benchmark_sym, e)

        bars_map = await fetch_all_daily_bars(ib, contracts_for_bars, pacing, duration=duration)
    else:
        log.info("Skipping historical daily bars (fetch_daily_bars=False)")

    # ── Step 3: market snapshots ───────────────────────────────────────────────
    snapshots = {}
    if app_config and app_config.ib_data.fetch_market_snapshot:
        snapshots = await fetch_market_snapshots(ib, contracts, pacing)
    else:
        log.info("Skipping market snapshots (fetch_market_snapshot=False)")

    # ── Step 4: pre-market 1-min bars (high, low, rvol) ───────────────────────
    premarket_map = {}
    if app_config and app_config.ib_data.fetch_pre_market_bars:
        log.info("Fetching pre-market 1-min bars for %d symbols...", len(contracts))
        premarket_map = await fetch_all_premarket_bars(ib, contracts, pacing)
    else:
        log.info("Skipping pre-market 1-min bars (fetch_pre_market_bars=False)")

    # ── Step 5: previous session VWAP ─────────────────────────────────────────
    vwap_map = {}
    if app_config and app_config.ib_data.fetch_prev_session_vwap:
        log.info("Fetching previous-session VWAP for %d symbols...", len(contracts))
        vwap_map = await fetch_all_prev_session_vwap(ib, contracts, pacing)
    else:
        log.info("Skipping previous-session VWAP (fetch_prev_session_vwap=False)")

    # ── Step 6: benchmark snapshot ─────────────────────────────────────────────
    benchmark_sym = getattr(app_config, "benchmark_symbol", "SPY") if app_config else "SPY"
    bm_prev_close: float | None = None
    bm_chg_pct:   float | None = None
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
            yf_bm_data = await fetch_yfinance_data([benchmark_sym])
            if bm_data := yf_bm_data.get(benchmark_sym):
                bm_prev_close = bm_data.get("prev_close")
                bm_chg_pct = bm_data.get("pre_market_chg_pct")
        except Exception as e:
            log.warning("Benchmark fetch failed for %s from yfinance: %s", benchmark_sym, e)
    else:
        log.info("Skipping benchmark snapshot (output_benchmark_data set to null or not configured)")

    if bm_prev_close is not None:
        log.info("Benchmark %s: close=%.2f  chg=%s%%",
                 benchmark_sym,
                 bm_prev_close or 0.0,
                 f"{bm_chg_pct:+.2f}" if bm_chg_pct is not None else "n/a")

    # ── Step 7: volume profiles ────────────────────────────────────────────────
    vp_map = {}
    if app_config and app_config.ib_data.fetch_volume_profile:
        lookback = 3  # default; screener config not available in watchlist mode
        log.info("Fetching volume profiles for %d symbols...", len(contracts))
        vp_map = await fetch_all_volume_profiles(ib, contracts, pacing,
                                                 lookback_sessions=lookback)
    else:
        log.info("Skipping volume profiles (fetch_volume_profile=False)")

    # ── Step 8: assemble records (no filters — all symbols included) ───────────
    build_kwargs = {}
    if app_config:
        # Only pass atr_period if output_atr is not None
        if app_config.ib_data.output_atr is not None:
            build_kwargs["atr_period"] = app_config.ib_data.atr_period
        
        # Only pass ema_periods if output_ema is not None
        if app_config.ib_data.output_ema is not None:
            build_kwargs["ema_periods"] = app_config.ib_data.ema_periods
            
        # Only pass rsi_period if output_rsi is not None
        if app_config.ib_data.output_rsi is not None:
            build_kwargs["rsi_period"] = app_config.ib_data.rsi_period
    
    records = build_records(
        contract_infos,
        snapshots,
        bars_map,
        app_config=app_config, # Pass app_config directly
        **build_kwargs,
    )

    # Helper to check if an output flag is not None, or is set to a specific source.
    # Defined here to access app_config in the current scope.
    def _should_output_ib_data(flag_name: str, source: str | None = None) -> bool:
        if not (app_config and hasattr(app_config.ib_data, flag_name)):
            return False
        val = getattr(app_config.ib_data, flag_name)
        if source:
            return val == source
        return val is not None

    def _should_output_external_data(flag_name: str, source: str | None = None) -> bool:
        if not (app_config and hasattr(app_config.external_apis, flag_name)):
            return False
        val = getattr(app_config.external_apis, flag_name)
        if source:
            return val == source
        return val is not None

    # ── Step 9: patch records with pre-market bars, VWAP, benchmark, VP ───────
    if app_config and _should_output_ib_data("output_vp_poc", source="yfinance"):
        log.warning(
            "Volume Profile from yfinance is not supported "
            "(requires per-price histogram data) and will be null."
        )

    for rec in records:
        # Patching pre-market bars
        pm = premarket_map.get(rec.symbol)
        if pm:
            if _should_output_ib_data("output_pre_market_high"):
                rec.pre_market_high = pm.pre_market_high
            else:
                rec.pre_market_high = None
            if _should_output_ib_data("output_pre_market_low"):
                rec.pre_market_low  = pm.pre_market_low
            else:
                rec.pre_market_low = None
            if _should_output_ib_data("output_rvol_pre_market"):
                rec.rvol_pre_market = pm.rvol_pre_market
            else:
                rec.rvol_pre_market = None
            # Use TRADES-bar sum as pre_market_volume (SIP composite, matches TradingView)
            # when available — more accurate than the streaming ticker.volume tick
            if (pm.pre_market_volume is not None
                    and _should_output_ib_data("output_pre_market_volume", source="ibk")):
                rec.pre_market_volume = pm.pre_market_volume
        else: # If premarket data is not available, explicitly set to None if flags are set
            if _should_output_ib_data("output_pre_market_high"):
                rec.pre_market_high = None
            if _should_output_ib_data("output_pre_market_low"):
                rec.pre_market_low = None
            if _should_output_ib_data("output_rvol_pre_market"):
                rec.rvol_pre_market = None

        # Patching previous session VWAP (finhub branch populated later from yf_data)
        if _should_output_ib_data("output_vwap_prev_session", source="ibk"):
            rec.vwap_prev_session = vwap_map.get(rec.symbol)
        else:
            rec.vwap_prev_session = None

        # Patching benchmark data
        if _should_output_ib_data("output_benchmark_data"): # Master switch for benchmark data
            rec.benchmark_symbol = benchmark_sym # Symbol is always displayed if benchmark data is active
            if _should_output_ib_data("output_benchmark_prev_close"):
                rec.benchmark_prev_close         = bm_prev_close
            else:
                rec.benchmark_prev_close = None
            if _should_output_ib_data("output_benchmark_pre_market_chg_pct"):
                rec.benchmark_pre_market_chg_pct = bm_chg_pct
            else:
                rec.benchmark_pre_market_chg_pct = None
        else:
            rec.benchmark_symbol = None
            rec.benchmark_prev_close = None
            rec.benchmark_pre_market_chg_pct = None

        # Patching volume profile data
        vp = vp_map.get(rec.symbol)
        rec.vp_lookback_sessions = vp.lookback_sessions if vp else None # Informational field

        if _should_output_ib_data("output_vp_poc", source="ibk"):
            rec.vp_poc = vp.poc if vp else None
        elif _should_output_ib_data("output_vp_poc", source="yfinance"):
            rec.vp_poc = None # Not supported from yfinance
        else:
            rec.vp_poc = None

        if _should_output_ib_data("output_vp_vah", source="ibk"):
            rec.vp_vah = vp.vah if vp else None
        elif _should_output_ib_data("output_vp_vah", source="yfinance"):
            rec.vp_vah = None # Not supported from yfinance
        else:
            rec.vp_vah = None

        if _should_output_ib_data("output_vp_val", source="ibk"):
            rec.vp_val = vp.val if vp else None
        elif _should_output_ib_data("output_vp_val", source="yfinance"):
            rec.vp_val = None # Not supported from yfinance
        else:
            rec.vp_val = None

        # Patching beta from calculated values
        if _should_output_ib_data("output_beta", source="calculated"):
            stock_bars = bars_map.get(rec.symbol)
            bench_bars = bars_map.get(benchmark_sym)
            if stock_bars and bench_bars:
                rec.beta = _compute_beta(stock_bars, bench_bars)
            else:
                rec.beta = None
        # Note: 'ibk' and 'finhub' beta sources are handled later during enrichment patching


    # ── Step 10: external enrichment (yfinance + FMP) — best-effort ───────────
    syms = [rec.symbol for rec in records]
    ext_cfg = getattr(app_config, "external_apis", None) if app_config else None
    ib_data_cfg = getattr(app_config, "ib_data", None) if app_config else None

    yf_data: dict = {}
    # Determine if any fields require fetching data from yfinance
    needs_yfinance = False
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

        if any(_should_output_ib_data(f, "yfinance") for f in ib_finhub) or \
           any(_should_output_external_data(f, "yfinance") for f in ext_finhub):
            needs_yfinance = True

    if needs_yfinance:
        log.info("Fetching external data (yfinance) for %d symbols...", len(syms))
        rvol_lookback = getattr(getattr(app_config, "ib_data", None), "pre_market_rvol_lookback", 5) if app_config else 5
        yf_data = await fetch_yfinance_data(syms, rvol_lookback_days=min(rvol_lookback, 5))
    else:
        log.info("Skipping yfinance fetch (no fields are configured to use 'finhub' as a source)")

    news_data: dict = {}
    fmp_key = getattr(ext_cfg, "fmp_api_key", "") if ext_cfg else ""
    max_headlines = getattr(ext_cfg, "news_max_headlines", 3) if ext_cfg else 3
    if fmp_key and max_headlines > 0 and _should_output_external_data("output_news_catalysts", source="yfinance"):
        log.info("Fetching news catalysts via FMP for %d symbols...", len(syms))
        news_data = await fetch_news_catalysts(syms, fmp_key, max_headlines)
    else:
        log.info("Skipping news fetch (API key/flag not set or output disabled)")

    finnhub_volume: dict = {}
    finnhub_key = getattr(ext_cfg, "finnhub_api_key", "") if ext_cfg else ""
    if finnhub_key and ib_data_cfg and ib_data_cfg.output_pre_market_volume == "finnhub":
        from src.external.finnhub_data import fetch_finnhub_premarket_volume
        log.info("Fetching pre-market volume from Finnhub for %d symbols...", len(syms))
        finnhub_volume = await fetch_finnhub_premarket_volume(syms, finnhub_key)
    elif ib_data_cfg and ib_data_cfg.output_pre_market_volume == "finnhub":
        log.warning("output_pre_market_volume=finnhub but finnhub_api_key is not set — falling back to IB volume")

    if finnhub_volume:
        for rec in records:
            vol = finnhub_volume.get(rec.symbol)
            if vol is not None:
                rec.pre_market_volume = vol

    for rec in records:
        ext_cfg = getattr(app_config, "external_apis", None) if app_config else None
        ib_data_cfg = getattr(app_config, "ib_data", None) if app_config else None

        # Handle yfinance data
        if yf := yf_data.get(rec.symbol):
            # Next earnings date
            if _should_output_external_data("output_next_earnings_date"):
                rec.next_earnings_date = yf.get("next_earnings_date")
            else:
                rec.next_earnings_date = None # Output flag is None
            
            # Short float, short ratio, institutional holding
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
            
            # Conditional patching of fields from yfinance based on settings.yaml for IB_DATA fields
            if ib_data_cfg:
                # shares_outstanding
                # Only overwrite with yf data if output_shares_outstanding is not "ibk" AND not None
                if ib_data_cfg.output_shares_outstanding != "ibk" and ib_data_cfg.output_shares_outstanding is not None:
                    rec.shares_outstanding = yf.get("shares_outstanding")
                elif ib_data_cfg.output_shares_outstanding is None:
                    rec.shares_outstanding = None
                
                # market_cap_usd
                if ib_data_cfg.output_market_cap != "ibk" and ib_data_cfg.output_market_cap is not None:
                    rec.market_cap_usd = yf.get("market_cap_usd")
                elif ib_data_cfg.output_market_cap is None:
                    rec.market_cap_usd = None

                # price (previous close)
                if ib_data_cfg.output_prev_close != "ibk" and ib_data_cfg.output_prev_close is not None:
                    rec.price = yf.get("prev_close")
                elif ib_data_cfg.output_prev_close is None:
                    rec.price = None

                # fifty_two_week_high
                if ib_data_cfg.output_fifty_two_week_high != "ibk" and ib_data_cfg.output_fifty_two_week_high is not None:
                    rec.fifty_two_week_high = yf.get("fifty_two_week_high")
                elif ib_data_cfg.output_fifty_two_week_high is None:
                    rec.fifty_two_week_high = None
                
                # fifty_two_week_low
                if ib_data_cfg.output_fifty_two_week_low != "ibk" and ib_data_cfg.output_fifty_two_week_low is not None:
                    rec.fifty_two_week_low = yf.get("fifty_two_week_low")
                elif ib_data_cfg.output_fifty_two_week_low is None:
                    rec.fifty_two_week_low = None
                
                # beta
                if ib_data_cfg.output_beta == "yfinance":
                    rec.beta = yf.get("beta")
                elif ib_data_cfg.output_beta is None:
                    rec.beta = None

                # pre-market high/low/rvol from yfinance 1-min bars
                if ib_data_cfg.output_pre_market_high == "yfinance":
                    rec.pre_market_high = yf.get("pre_market_high")
                if ib_data_cfg.output_pre_market_low == "yfinance":
                    rec.pre_market_low = yf.get("pre_market_low")
                if ib_data_cfg.output_rvol_pre_market == "yfinance":
                    rec.rvol_pre_market = yf.get("rvol_pre_market")

                # prev-session VWAP from yfinance 1-min bars
                if ib_data_cfg.output_vwap_prev_session == "yfinance":
                    rec.vwap_prev_session = yf.get("vwap_prev_session")

                # pre-market volume from yfinance info.preMarketVolume (consolidated, matches TradingView)
                if ib_data_cfg.output_pre_market_volume == "yfinance":
                    yf_pmv = yf.get("pre_market_volume")
                    if yf_pmv is not None:
                        rec.pre_market_volume = yf_pmv

            # Float shares as percentage of outstanding — MUST run after shares_outstanding is patched
            if _should_output_external_data("output_float_pct", source="yfinance"):
                raw_float_shares = yf.get("float_shares")
                if raw_float_shares is not None and rec.shares_outstanding is not None and rec.shares_outstanding > 0:
                    rec.float_pct = (raw_float_shares / rec.shares_outstanding) * 100
                else:
                    rec.float_pct = None # Cannot calculate percentage if shares_outstanding is missing or zero.
            else:
                rec.float_pct = None # Output flag is None
            
            # Handle calculated fields from yfinance history
            history_df = yf.get("history")
            if history_df is not None and not history_df.empty and ib_data_cfg:
                log.debug("%s: calculating indicators from yfinance history", rec.symbol)

                # Drop rows with incomplete OHLC (e.g. current in-progress trading day
                # returned by yfinance with NaN values) so iloc[-1] is always a complete bar.
                history_df = history_df.dropna(subset=['High', 'Low', 'Close', 'Open'])

                # Previous Day OHL
                if len(history_df) >= 2:
                    if ib_data_cfg.output_prev_day_high == "yfinance":
                        rec.prev_day_high = history_df['High'].iloc[-2]
                    if ib_data_cfg.output_prev_day_low == "yfinance":
                        rec.prev_day_low = history_df['Low'].iloc[-2]
                    if ib_data_cfg.output_prev_day_open == "yfinance":
                        rec.prev_day_open = history_df['Open'].iloc[-2]

                # Average Daily Volume
                if ib_data_cfg.output_avg_daily_volume_20d == "yfinance":
                    rec.avg_daily_volume_20d = history_df['Volume'].tail(20).mean()

                # ATR
                if ib_data_cfg.output_atr == "yfinance":
                    atr_period = app_config.ib_data.atr_period if app_config else 14
                    if len(history_df) >= atr_period + 1:
                        high_low = history_df['High'] - history_df['Low']
                        high_close = (history_df['High'] - history_df['Close'].shift()).abs()
                        low_close = (history_df['Low'] - history_df['Close'].shift()).abs()
                        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                        atr_series = tr.ewm(com=atr_period - 1, min_periods=atr_period, adjust=False).mean()
                        atr = atr_series.iloc[-1]
                        last_close = history_df['Close'].iloc[-1]
                        if pd.notna(atr) and last_close > 0:
                            rec.atr = round(float(atr) / last_close * 100, 2)
                
                # EMA
                if ib_data_cfg.output_ema == "yfinance":
                    ema_periods = app_config.ib_data.ema_periods if app_config else []
                    for p in ema_periods:
                        if len(history_df) >= p:
                            ema = history_df['Close'].ewm(span=p, adjust=False).mean().iloc[-1]
                            rec.emas[p] = round(ema, 4)
                            
                # RSI
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
                            rsi = 100 - (100 / (1 + rs))
                            rec.rsi_14 = round(rsi.iloc[-1], 2)
        else: # If yfinance data is NOT available for this symbol
            # Explicitly set yfinance-sourced fields to None if their flags are set
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
            
            # Also, for IB_DATA fields configured to use external source, set them to None if external data missing
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

        # Handle news catalysts
        if _should_output_external_data("output_news_catalysts", source="yfinance"):
            rec.news_catalysts = news_data.get(rec.symbol, [])
        else:
            rec.news_catalysts = [] # Output flag is None or not configured

    # ── Step 11: Post-enrichment calculations ────────────────────────────────
    if (app_config and app_config.ib_data.output_market_cap is not None
            and app_config.ib_data.output_avg_daily_volume_20d is not None):
        log.info("Calculating mc_vol_ratio for records...")
        for rec in records:
            if rec.market_cap_usd and rec.avg_daily_volume_20d and rec.avg_daily_volume_20d > 0:
                rec.mc_vol_ratio = round(rec.market_cap_usd / rec.avg_daily_volume_20d, 2)

    duration = time.monotonic() - start_time
    log.info("Watchlist data collection finished in %.2f minutes", duration / 60)

    return records


async def run_watchlist_pipeline(
    app_config: AppConfig,
    watchlist: List[WatchlistEntry],
    dry_run: bool = False,
) -> Path:
    """
    Watchlist pipeline:
      contract details → historical bars → market snapshots
      → pre-market bars → VWAP → benchmark → volume profiles
      → build records → external enrichment → write YAML

    All watchlist symbols always appear in output (no filtering applied).
    Missing data fields appear as null in the YAML.
    """
    async with IBClient(app_config.ib_gateway) as ib:
        records = await collect_watchlist_records(ib, watchlist, app_config.pacing, app_config)

    if dry_run:
        log.info("[dry-run] Would write %d records to %s",
                 len(records), app_config.output.directory)
        return Path(app_config.output.directory) / "dry_run.json"

    return write_output(
        records, app_config,
    )
