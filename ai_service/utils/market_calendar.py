from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

_NYSE = mcal.get_calendar("NYSE")
_ET = ZoneInfo("America/New_York")

# Generous enough to span any real-world holiday cluster (e.g. Christmas/New
# Year's back-to-back closures) while staying a cheap, bounded schedule query.
_LOOKBACK_DAYS = 10


def last_market_close(now: datetime | None = None) -> datetime:
    """Return the most recent NYSE close at or before `now`, tz-aware in America/New_York.

    Uses the exchange's real holiday schedule (via pandas_market_calendars) so
    the result correctly carries back over weekends and holidays to the last
    actual trading day, and reflects the real close time on early-close days
    (e.g. 13:00 ET) rather than assuming every trading day closes at 16:00.
    """
    now = (now or datetime.now(_ET)).astimezone(_ET)
    start = now - timedelta(days=_LOOKBACK_DAYS)
    schedule = _NYSE.schedule(start_date=start.date(), end_date=now.date())
    closes = schedule["market_close"].dt.tz_convert(_ET)
    past_closes = closes[closes <= now]
    if past_closes.empty:
        # Defensive fallback — shouldn't happen with a 10-day lookback, but
        # search freshness filtering must never crash the pipeline over this.
        return now - timedelta(days=_LOOKBACK_DAYS)
    return past_closes.iloc[-1].to_pydatetime()
