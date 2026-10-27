"""Europe/London market-day and cut-off helpers. Stored times are UTC epoch seconds."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
SLOT = 1800


def _epoch(d: date, t: time) -> int:
    return int(datetime.combine(d, t, tzinfo=LONDON).timestamp())


def market_day_slots(d: date) -> list[int]:
    """UTC start of every half-hour slot of London calendar day `d` (46, 48 or 50 slots)."""
    return list(range(_epoch(d, time(0)), _epoch(d + timedelta(days=1), time(0)), SLOT))


def decision_cutoff(delivery: date, cutoff_time: time = time(9, 20)) -> int:
    """Cut-off for delivery day `delivery`: `cutoff_time` London wall-clock on the day before.

    A wall-clock time that does not exist (spring-forward gap) is moved forward by zoneinfo.
    """
    return _epoch(delivery - timedelta(days=1), cutoff_time)


def hour_floor(ts: int) -> int:
    """Start of the UTC hour containing ts (London offsets are whole hours, so this is also the local hour start)."""
    return ts - ts % 3600


def london_hour(ts: int) -> int:
    return datetime.fromtimestamp(ts, tz=LONDON).hour


def london_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, tz=LONDON).date()
