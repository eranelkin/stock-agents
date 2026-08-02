from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_PM_START = datetime.time(4, 0)
_PM_END   = datetime.time(9, 30)


def _fetch_yfinance_sync(symbols: List[str], rvol_lookback_days: int = 5) -> Dict[str, dict]:
    """Synchronous yfinance fetch — called via asyncio.to_thread() to avoid blocking the IB loop."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed — float_shares and next_earnings_date will be null")
        return {}

    results: Dict[str, dict] = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info   = ticker.info or {}

            float_shares: Optional[float] = None
            raw_float = info.get("floatShares")
            if raw_float is not None:
                try:
                    float_shares = float(raw_float)
                except (TypeError, ValueError):
                    pass

            next_date: Optional[str] = None
            # Try fetching from ticker.info first, as it's often more direct for the next earnings date
            raw_earnings_date_info = info.get("earningsDate")
            if raw_earnings_date_info is not None:
                try:
                    # yfinance can return a list of timestamps, take the first one
                    ts = raw_earnings_date_info
                    if isinstance(ts, list) and ts:
                        ts = ts[0]

                    # yfinance returns timestamps, convert to datetime and then string
                    earnings_datetime = datetime.datetime.fromtimestamp(ts)
                    next_date = earnings_datetime.strftime("%Y-%m-%d")
                except (TypeError, ValueError, AttributeError):
                    pass

            # Fallback to ticker.calendar if info.get("earningsDate") is not available or failed.
            # yfinance 1.x returns a plain dict; older versions returned a DataFrame.
            if next_date is None:
                try:
                    cal = ticker.calendar
                    if isinstance(cal, dict):
                        ed_list = cal.get("Earnings Date")
                        if ed_list:
                            ed = ed_list[0] if isinstance(ed_list, list) else ed_list
                            next_date = str(ed)[:10]  # datetime.date -> "YYYY-MM-DD"
                    elif cal is not None and not cal.empty:
                        # Legacy DataFrame format (yfinance < 1.x)
                        ed = (
                            cal.loc["Earnings Date"].iloc[0]
                            if "Earnings Date" in cal.index
                            else None
                        )
                        if ed is not None:
                            next_date = str(ed)[:10]
                except Exception:
                    pass

            # Extract additional overlapping fields from yfinance info
            shares_outstanding: Optional[float] = None
            raw_so = info.get("sharesOutstanding")
            if raw_so is not None:
                try:
                    shares_outstanding = float(raw_so)
                except (TypeError, ValueError):
                    pass

            market_cap_usd: Optional[float] = None
            raw_mc = info.get("marketCap")
            if raw_mc is not None:
                try:
                    market_cap_usd = float(raw_mc)
                except (TypeError, ValueError):
                    pass
            
            prev_close: Optional[float] = None
            raw_pc = info.get("previousClose")
            if raw_pc is not None:
                try:
                    prev_close = float(raw_pc)
                except (TypeError, ValueError):
                    pass

            fifty_two_week_high: Optional[float] = None
            raw_fwh = info.get("fiftyTwoWeekHigh")
            if raw_fwh is not None:
                try:
                    fifty_two_week_high = float(raw_fwh)
                except (TypeError, ValueError):
                    pass
            
            fifty_two_week_low: Optional[float] = None
            raw_fwl = info.get("fiftyTwoWeekLow")
            if raw_fwl is not None:
                try:
                    fifty_two_week_low = float(raw_fwl)
                except (TypeError, ValueError):
                    pass

            beta: Optional[float] = None
            raw_beta = info.get("beta")
            if raw_beta is not None:
                try:
                    beta = float(raw_beta)
                except (TypeError, ValueError):
                    pass

            pre_market_chg_pct: Optional[float] = None
            raw_pm_chg_pct = info.get("preMarketChangePercent")
            if raw_pm_chg_pct is not None:
                try:
                    # yfinance provides this as a ratio (e.g., 0.01), convert to percent
                    pre_market_chg_pct = float(raw_pm_chg_pct) * 100
                except (TypeError, ValueError):
                    pass

            short_float_pct: Optional[float] = None
            raw_sfp = info.get("shortPercentOfFloat")
            if raw_sfp is not None:
                try:
                    # yfinance provides this as a ratio (e.g., 0.05), convert to percent
                    short_float_pct = float(raw_sfp) * 100
                except (TypeError, ValueError):
                    pass
            
            short_ratio: Optional[float] = None
            raw_sr = info.get("shortRatio")
            if raw_sr is not None:
                try:
                    short_ratio = float(raw_sr)
                except (TypeError, ValueError):
                    pass

            institutional_holding_pct: Optional[float] = None
            raw_ihp = info.get("heldPercentInstitutions")
            if raw_ihp is not None:
                try:
                    # yfinance provides this as a ratio (e.g., 0.85), convert to percent
                    institutional_holding_pct = float(raw_ihp) * 100
                except (TypeError, ValueError):
                    pass

            history = ticker.history(period="1y")

            # ── Intraday 1-min bars: pre-market high/low/rvol + prev-session VWAP ──
            pre_market_high: Optional[float] = None
            pre_market_low:  Optional[float] = None
            rvol_pre_market: Optional[float] = None
            vwap_prev_session: Optional[float] = None
            _lookback = min(rvol_lookback_days, 5)  # yfinance 1m capped at ~7 cal days

            try:
                pm_df = ticker.history(
                    interval="1m", prepost=True,
                    period=f"{_lookback + 2}d",
                )
                if pm_df is not None and not pm_df.empty:
                    if pm_df.index.tz is not None:
                        pm_df = pm_df.tz_convert("America/New_York")
                    else:
                        pm_df = pm_df.tz_localize("UTC").tz_convert("America/New_York")
                    bar_times = pm_df.index.time
                    pm_df = pm_df[(bar_times >= _PM_START) & (bar_times < _PM_END)].copy()

                    if not pm_df.empty:
                        pm_df["_date"] = pm_df.index.date
                        all_dates = sorted(pm_df["_date"].unique())
                        today_dt  = all_dates[-1]
                        prior_dts = all_dates[:-1]

                        today_pm = pm_df[pm_df["_date"] == today_dt]
                        if not today_pm.empty:
                            pre_market_high = float(today_pm["High"].max())
                            pre_market_low  = float(today_pm["Low"].min())
                            today_vol   = float(today_pm["Volume"].sum())
                            latest_t    = today_pm.index.time.max()

                            prior_vols = []
                            for d in prior_dts:
                                day_pm = pm_df[pm_df["_date"] == d]
                                vol = float(day_pm[day_pm.index.time <= latest_t]["Volume"].sum())
                                if vol > 0:
                                    prior_vols.append(vol)

                            if prior_vols:
                                rvol_pre_market = round(today_vol / (sum(prior_vols) / len(prior_vols)), 2)
            except Exception as e:
                log.debug("%s: yfinance pre-market bars failed: %s", sym, e)

            try:
                rth_df = ticker.history(interval="1m", prepost=False, period="2d")
                if rth_df is not None and not rth_df.empty:
                    if rth_df.index.tz is not None:
                        rth_df = rth_df.tz_convert("America/New_York")
                    else:
                        rth_df = rth_df.tz_localize("UTC").tz_convert("America/New_York")
                    rth_df["_date"] = rth_df.index.date
                    rth_dates = sorted(rth_df["_date"].unique())
                    if len(rth_dates) >= 2:
                        prior_rth  = rth_df[rth_df["_date"] == rth_dates[-2]]
                        total_vol  = float(prior_rth["Volume"].sum())
                        if total_vol > 0:
                            vwap_val = float((prior_rth["Close"] * prior_rth["Volume"]).sum()) / total_vol
                            vwap_prev_session = round(vwap_val, 4)
            except Exception as e:
                log.debug("%s: yfinance VWAP bars failed: %s", sym, e)

            results[sym] = {
                "pre_market_chg_pct": pre_market_chg_pct,
                "float_shares":       float_shares,
                "next_earnings_date": next_date,
                "shares_outstanding": shares_outstanding,
                "market_cap_usd":     market_cap_usd,
                "prev_close":         prev_close,
                "fifty_two_week_high":fifty_two_week_high,
                "fifty_two_week_low": fifty_two_week_low,
                "beta":               beta,
                "short_float_pct":    short_float_pct,
                "short_ratio":        short_ratio,
                "institutional_holding_pct": institutional_holding_pct,
                "history":            history,
                "pre_market_high":    pre_market_high,
                "pre_market_low":     pre_market_low,
                "rvol_pre_market":    rvol_pre_market,
                "vwap_prev_session":  vwap_prev_session,
            }
        except Exception as e:
            log.warning("%s: yfinance fetch failed: %s", sym, e)
            results[sym] = {
                "float_shares":       None,
                "next_earnings_date": None,
                "shares_outstanding": None,
                "market_cap_usd":     None,
                "prev_close":         None,
                "fifty_two_week_high":None,
                "fifty_two_week_low": None,
                "beta":               None,
                "short_float_pct":    None,
                "short_ratio":        None,
                "institutional_holding_pct": None,
                "history":            None,
                "pre_market_chg_pct": None,
                "pre_market_high":    None,
                "pre_market_low":     None,
                "rvol_pre_market":    None,
                "vwap_prev_session":  None,
            }

    return results


async def fetch_yfinance_data(symbols: List[str], rvol_lookback_days: int = 5) -> Dict[str, dict]:
    """Fetch external data for all symbols via yfinance, including 1-min intraday bars."""
    if not symbols:
        return {}
    return await asyncio.to_thread(_fetch_yfinance_sync, symbols, rvol_lookback_days)
