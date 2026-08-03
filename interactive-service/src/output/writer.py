from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import json

from src.config.loader import AppConfig, IBDataConfig
from src.processing.enrichment import StockRecord

log = logging.getLogger(__name__)


# ── Formatters ─────────────────────────────────────────────────────────────────

def _fmt_market_cap(usd: Optional[float]) -> Optional[str]:
    if usd is None:
        return None
    if usd >= 1_000_000_000:
        return f"{usd / 1_000_000_000:.2f}B"
    if usd >= 1_000_000:
        return f"{usd / 1_000_000:.2f}M"
    return f"{usd:.0f}"


def _fmt_chg_pct(pct: Optional[float]) -> Optional[str]:
    if pct is None:
        return None
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _fmt_volume(vol: Optional[float]) -> Optional[str]:
    if vol is None:
        return None
    if vol >= 1_000_000:
        return f"{vol / 1_000_000:.2f}M"
    if vol >= 1_000:
        return f"{vol / 1_000:.2f}K"
    return f"{vol:.0f}"


def _fmt_price(price: Optional[float]) -> Optional[float]:
    if price is None:
        return None
    return round(price, 2)


def _fmt_pct(val: Optional[float]) -> Optional[str]:
    if val is None:
        return None
    return f"{val:.2f}%"


def _fmt_beta(val: Optional[float]) -> Optional[float]:
    return round(val, 3) if val is not None else None


def _fmt_ratio(val: Optional[float]) -> Optional[float]:
    return round(val, 2) if val is not None else None


# ── Serialisation ──────────────────────────────────────────────────────────────

def _record_to_dict(rec: StockRecord, app_cfg: AppConfig) -> dict:
    """Convert a StockRecord to a dictionary based on IBDataConfig flags."""
    ib_cfg = app_cfg.ib_data
    ext_cfg = app_cfg.external_apis
    data = {"symbol": rec.symbol}

    # ── Identity & Contract details ──────────────────────────────────────────
    if ib_cfg.output_company_name:
        data["company_name"] = rec.company_name or f"Not available from source ({ib_cfg.output_company_name})"
    if ib_cfg.output_sector:
        data["sector"] = rec.sector or f"Not available from source ({ib_cfg.output_sector})"
    if ib_cfg.output_industry:
        data["industry"] = rec.industry or f"Not available from source ({ib_cfg.output_industry})"

    # ── Market snapshot data ─────────────────────────────────────────────────
    if ib_cfg.output_market_cap:
        if rec.market_cap_usd is not None:
            data["market_cap"] = _fmt_market_cap(rec.market_cap_usd)
        else:
            data["market_cap"] = f"Not available from source ({ib_cfg.output_market_cap})"
    if ib_cfg.output_shares_outstanding:
        if rec.shares_outstanding is not None:
            data["shares_outstanding"] = _fmt_market_cap(rec.shares_outstanding)
        else:
            data["shares_outstanding"] = f"Not available from source ({ib_cfg.output_shares_outstanding})"
    if ib_cfg.output_beta:
        beta_val = _fmt_beta(rec.beta)
        if rec.beta is None:
            beta_val = f"Not available from source ({ib_cfg.output_beta})"
        data["beta"] = {"value": beta_val, "timeframe": ib_cfg.beta_timeframe}
    if ib_cfg.output_fifty_two_week_high:
        if rec.fifty_two_week_high is not None:
            data["fifty_two_week_high"] = _fmt_price(rec.fifty_two_week_high)
        else:
            data["fifty_two_week_high"] = f"Not available from source ({ib_cfg.output_fifty_two_week_high})"
    if ib_cfg.output_fifty_two_week_low:
        if rec.fifty_two_week_low is not None:
            data["fifty_two_week_low"] = _fmt_price(rec.fifty_two_week_low)
        else:
            data["fifty_two_week_low"] = f"Not available from source ({ib_cfg.output_fifty_two_week_low})"
    if ib_cfg.output_pre_market_price:
        if rec.pre_market_price is not None:
            data["pre_market_price"] = _fmt_price(rec.pre_market_price)
        else:
            data["pre_market_price"] = f"Not available from source ({ib_cfg.output_pre_market_price})"
    if ib_cfg.output_pre_market_chg_pct:
        if rec.pre_market_chg_pct is not None:
            data["pre_market_chg_pct"] = _fmt_chg_pct(rec.pre_market_chg_pct)
        else:
            data["pre_market_chg_pct"] = f"Not available from source ({ib_cfg.output_pre_market_chg_pct})"
    if ib_cfg.output_pre_market_volume:
        if rec.pre_market_volume is not None:
            data["pre_market_volume"] = _fmt_volume(rec.pre_market_volume)
        else:
            data["pre_market_volume"] = f"Not available from source ({ib_cfg.output_pre_market_volume})"

    # ── External: yfinance data ──────────────────────────────────────────────
    if ext_cfg.output_float_pct:
        if rec.float_pct is not None:
            data["float_pct"] = _fmt_pct(rec.float_pct)
        else:
            data["float_pct"] = f"Not available from source ({ext_cfg.output_float_pct})"
    if ext_cfg.output_next_earnings_date:
        data["next_earnings_date"] = rec.next_earnings_date or f"Not available from source ({ext_cfg.output_next_earnings_date})"
    if ext_cfg.output_short_float_pct:
        if rec.short_float_pct is not None:
            data["short_float_pct"] = _fmt_pct(rec.short_float_pct)
        else:
            data["short_float_pct"] = f"Not available from source ({ext_cfg.output_short_float_pct})"
    if ext_cfg.output_short_ratio:
        if rec.short_ratio is not None:
            data["short_ratio"] = _fmt_ratio(rec.short_ratio)
        else:
            data["short_ratio"] = f"Not available from source ({ext_cfg.output_short_ratio})"
    if ext_cfg.output_institutional_holding_pct:
        if rec.institutional_holding_pct is not None:
            data["institutional_holding_pct"] = _fmt_pct(rec.institutional_holding_pct)
        else:
            data["institutional_holding_pct"] = f"Not available from source ({ext_cfg.output_institutional_holding_pct})"

    # ── Pre-market bars data ─────────────────────────────────────────────────
    if ib_cfg.output_pre_market_high:
        if rec.pre_market_high is not None:
            data["pre_market_high"] = _fmt_price(rec.pre_market_high)
        else:
            data["pre_market_high"] = f"Not available from source ({ib_cfg.output_pre_market_high})"
    if ib_cfg.output_pre_market_low:
        if rec.pre_market_low is not None:
            data["pre_market_low"] = _fmt_price(rec.pre_market_low)
        else:
            data["pre_market_low"] = f"Not available from source ({ib_cfg.output_pre_market_low})"
    if ib_cfg.output_rvol_pre_market:
        if rec.rvol_pre_market is not None:
            data["rvol_pre_market"] = _fmt_ratio(rec.rvol_pre_market)
        else:
            data["rvol_pre_market"] = f"Not calculated (source: {ib_cfg.output_rvol_pre_market})"

    # ── Daily bars data ──────────────────────────────────────────────────────
    if ib_cfg.output_prev_close:
        if rec.price is not None:
            data["prev_close"] = _fmt_price(rec.price)
        else:
            data["prev_close"] = f"Not available from source ({ib_cfg.output_prev_close})"
    if ib_cfg.output_prev_day_high:
        if rec.prev_day_high is not None:
            data["prev_day_high"] = _fmt_price(rec.prev_day_high)
        else:
            data["prev_day_high"] = f"Not available from source ({ib_cfg.output_prev_day_high})"
    if ib_cfg.output_prev_day_low:
        if rec.prev_day_low is not None:
            data["prev_day_low"] = _fmt_price(rec.prev_day_low)
        else:
            data["prev_day_low"] = f"Not available from source ({ib_cfg.output_prev_day_low})"
    if ib_cfg.output_prev_day_open:
        if rec.prev_day_open is not None:
            data["prev_day_open"] = _fmt_price(rec.prev_day_open)
        else:
            data["prev_day_open"] = f"Not available from source ({ib_cfg.output_prev_day_open})"
    if ib_cfg.output_avg_daily_volume_20d:
        if rec.avg_daily_volume_20d is not None:
            data["avg_daily_volume_20d"] = _fmt_volume(rec.avg_daily_volume_20d)
        else:
            data["avg_daily_volume_20d"] = f"Not available from source ({ib_cfg.output_avg_daily_volume_20d})"

    # ── Technical indicators ─────────────────────────────────────────────────
    if ib_cfg.output_atr:
        atr_val = _fmt_pct(rec.atr)
        if rec.atr is None:
            atr_val = f"Not calculated (source: {ib_cfg.output_atr}, not enough historical data?)"
        data["atr"] = {"value": atr_val, "period": ib_cfg.atr_period, "timeframe": "1d"}
    if ib_cfg.output_ema:
        ema_data: Dict[str, str | float | None] = {}
        for p in ib_cfg.ema_periods:
            val = rec.emas.get(p)
            if val is not None:
                ema_data[f"ema_{p}"] = _fmt_ratio(val)
            else:
                ema_data[f"ema_{p}"] = f"Not calculated (source: {ib_cfg.output_ema}, not enough historical data?)"
        ema_data["timeframe"] = ib_cfg.ema_timeframe
        data["ema"] = ema_data
    if ib_cfg.output_rsi:
        rsi_val = _fmt_ratio(rec.rsi_14)
        if rec.rsi_14 is None:
            rsi_val = f"Not calculated (source: {ib_cfg.output_rsi}, not enough historical data?)"
        data[f"rsi_{ib_cfg.rsi_period}"] = rsi_val

    # ── Other IB data ────────────────────────────────────────────────────────
    if ib_cfg.output_vwap_prev_session:
        if rec.vwap_prev_session is not None:
            data["vwap_prev_session"] = _fmt_price(rec.vwap_prev_session)
        else:
            data["vwap_prev_session"] = f"Not available from source ({ib_cfg.output_vwap_prev_session})"
    if ib_cfg.fetch_volume_profile and (ib_cfg.output_vp_poc or ib_cfg.output_vp_vah or ib_cfg.output_vp_val):
        vp_data = {}
        if ib_cfg.output_vp_poc:
            if rec.vp_poc is not None:
                vp_data["poc"] = _fmt_price(rec.vp_poc)
            else:
                vp_data["poc"] = f"Not available from source ({ib_cfg.output_vp_poc})"
        if ib_cfg.output_vp_vah:
            if rec.vp_vah is not None:
                vp_data["vah"] = _fmt_price(rec.vp_vah)
            else:
                vp_data["vah"] = f"Not available from source ({ib_cfg.output_vp_vah})"
        if ib_cfg.output_vp_val:
            if rec.vp_val is not None:
                vp_data["val"] = _fmt_price(rec.vp_val)
            else:
                vp_data["val"] = f"Not available from source ({ib_cfg.output_vp_val})"
        vp_data["lookback_sessions"] = rec.vp_lookback_sessions
        data["volume_profile"] = vp_data

    # ── Benchmark (SPY) ──────────────────────────────────────────────────────
    if ib_cfg.output_benchmark_data:
        bm_data = {"symbol": rec.benchmark_symbol or "N/A"}
        if ib_cfg.output_benchmark_prev_close:
            bm_data["prev_close"] = _fmt_price(rec.benchmark_prev_close) if rec.benchmark_prev_close is not None else None
        bm_data["pre_market_price"] = _fmt_price(rec.benchmark_pre_market_price) if rec.benchmark_pre_market_price is not None else None
        if ib_cfg.output_benchmark_pre_market_chg_pct:
            bm_data["pre_market_change_pct"] = _fmt_chg_pct(rec.benchmark_pre_market_chg_pct) if rec.benchmark_pre_market_chg_pct is not None else None
        data["benchmark"] = bm_data

    # ── External: News ───────────────────────────────────────────────────────
    if ext_cfg.output_news_catalysts:
        data["news_catalysts"] = rec.news_catalysts

    return data


def _sort_key(rec: StockRecord) -> float:
    return rec.pre_market_chg_pct if rec.pre_market_chg_pct is not None else float("-inf")


# ── Writer ─────────────────────────────────────────────────────────────────────

def write_output(
    records: List[StockRecord],
    app_config: AppConfig,
    max_stocks: Optional[int] = None,
) -> Path:
    """Sort records by pre-market change %, cap to top N, format fields, and write JSON file."""
    output_dir = Path(app_config.output.directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{app_config.output.filename_prefix}_{timestamp}.json"
    filepath = output_dir / filename

    sorted_records = sorted(records, key=_sort_key, reverse=True)
    if max_stocks is not None:
        sorted_records = sorted_records[:max_stocks]

    payload = {
        "stocks": [_record_to_dict(r, app_config) for r in sorted_records]
    }

    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log.info("Output written to %s (%d records)", filepath, len(sorted_records))
    return filepath
