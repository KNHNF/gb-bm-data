"""Settlement-period helpers. Internal module, not part of the public API.

GB settlement days run on Europe/London local time: period 1 starts at local
midnight, so on a BST day period 1 starts at 23:00 UTC the previous day, and
clock-change days have 46 or 50 half-hour periods. Periods are numbered by
elapsed real time since local midnight, which handles those days correctly.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def check_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError(f"start ({start}) is after end ({end}); dates are inclusive")


def settlement_day_window_utc(d: date) -> tuple[datetime, datetime]:
    """UTC start (inclusive) and next-day start (exclusive) of settlement day d."""
    start = datetime(d.year, d.month, d.day, tzinfo=LONDON).astimezone(timezone.utc)
    nxt = d + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=LONDON).astimezone(timezone.utc)
    return start, end


def to_settlement(ts: datetime) -> tuple[str, int]:
    """Settlement date (ISO string) and period number for an aware datetime."""
    local = ts.astimezone(LONDON)
    midnight = datetime(local.year, local.month, local.day, tzinfo=LONDON)
    elapsed_minutes = int((ts - midnight).total_seconds() // 60)
    return local.date().isoformat(), elapsed_minutes // 30 + 1
