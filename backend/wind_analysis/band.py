"""Uncertainty band from past decision-forecast errors, with no hindsight.

Only delivery days that had finished at the cut-off are used, and only actuals
published by the cut-off. If history is short the band is labelled; if there is
none, no band is returned (nothing is invented).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .config import AnalysisConfig
from .decision import decision_day
from .metrics import percentile
from .timeutil import SLOT, decision_cutoff, market_day_slots


@dataclass(frozen=True)
class Band:
    method: str                 # trailing_empirical | reduced_history | insufficient_history
    label: str
    n_days: int
    n_errors: int
    p10: float | None           # low percentile of (forecast - actual)
    p90: float | None           # high percentile of (forecast - actual)

    def interval(self, forecast: float) -> tuple[float, float] | None:
        """Range for the actual: actual = forecast - error, so [f - p90, f - p10]."""
        if self.p10 is None or self.p90 is None:
            return None
        return forecast - self.p90, forecast - self.p10


def uncertainty_band(src, delivery: date, cfg: AnalysisConfig = AnalysisConfig()) -> Band:
    cutoff = decision_cutoff(delivery, cfg.cutoff_time)
    errors: list[float] = []
    n_days = 0
    d = delivery - timedelta(days=1)
    looked_at = 0                                              # finished calendar days examined
    while looked_at < cfg.band_window_days:
        if market_day_slots(d)[-1] + SLOT <= cutoff:          # day had finished at the cut-off
            looked_at += 1
            day_errors = []
            for r in decision_day(src, d, cfg).slots:
                pub = src.actual_publish(r.slot)
                if r.error is not None and pub is not None and pub <= cutoff:
                    day_errors.append(r.error)
            if day_errors:
                errors += day_errors
                n_days += 1
        d -= timedelta(days=1)
    if n_days == 0:
        return Band("insufficient_history",
                    "Insufficient history: no finished days with data, so no band is shown",
                    0, 0, None, None)
    errors.sort()
    lo, hi = percentile(errors, cfg.band_lo), percentile(errors, cfg.band_hi)
    if n_days >= cfg.band_min_days:
        method = "trailing_empirical"
        label = f"Empirical P{cfg.band_lo:g}-P{cfg.band_hi:g} of past forecast errors over {n_days} finished days"
    else:
        method = "reduced_history"
        label = (f"Reduced history: only {n_days} finished day(s) available "
                 f"(target {cfg.band_min_days}); band is less reliable")
    return Band(method, label, n_days, len(errors), lo, hi)
