"""Decision forecast: for each half-hour of the delivery day, the latest vintage
published at or before the cut-off (inclusive). Missing stays missing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import AnalysisConfig
from .timeutil import decision_cutoff, hour_floor, market_day_slots


@dataclass(frozen=True)
class SlotRecord:
    slot: int                       # UTC epoch of slot start
    forecast: float | None          # hourly forecast covering this slot, as known at the cut-off
    vintage_publish: int | None     # publishTime of the vintage used
    lead_h: float | None            # slot start - vintage publish, hours
    actual: float | None            # ex-post actual (evaluation only)

    @property
    def error(self) -> float | None:
        if self.forecast is None or self.actual is None:
            return None
        return self.forecast - self.actual


@dataclass(frozen=True)
class DayDecision:
    day: date
    cutoff: int
    slots: tuple[SlotRecord, ...]
    n_slots: int
    n_missing_forecast: int
    n_missing_actual: int
    n_missing_both: int
    n_scored: int


def decision_day(src, delivery: date, cfg: AnalysisConfig = AnalysisConfig()) -> DayDecision:
    """`src` needs latest_forecast(target_hour, cutoff) and actual(slot)."""
    cutoff = decision_cutoff(delivery, cfg.cutoff_time)
    recs = []
    for slot in market_day_slots(delivery):
        lf = src.latest_forecast(hour_floor(slot), cutoff)
        pub, fc = (lf if lf is not None else (None, None))
        recs.append(SlotRecord(slot, fc, pub, None if pub is None else (slot - pub) / 3600, src.actual(slot)))
    mf = sum(1 for r in recs if r.forecast is None)
    ma = sum(1 for r in recs if r.actual is None)
    mb = sum(1 for r in recs if r.forecast is None and r.actual is None)
    return DayDecision(delivery, cutoff, tuple(recs), len(recs), mf, ma, mb, len(recs) - mf - ma + mb)
