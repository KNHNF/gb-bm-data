"""Official GB settlement date and period from UTC half-hour start times.

A settlement day runs from local midnight, so period 1 starts at 23:00 UTC the
day before during British Summer Time, and clock-change days have 46 or 50
periods. Internal module, not part of the public API."""
from __future__ import annotations

import pandas as pd

LOCAL_TZ = "Europe/London"


def to_settlement(utc_times: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return (settlement date as YYYY-MM-DD, settlement period) for tz-aware UTC times."""
    local = utc_times.dt.tz_convert(LOCAL_TZ)
    elapsed = (utc_times - local.dt.normalize()).dt.total_seconds()
    period = (elapsed // 1800).astype(int) + 1
    return local.dt.strftime("%Y-%m-%d"), period
