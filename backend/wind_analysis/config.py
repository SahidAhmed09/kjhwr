from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class AnalysisConfig:
    # Decision cut-off: Europe/London wall-clock time on the day before delivery (open decision D1).
    cutoff_time: time = time(9, 20)
    # Width of lead-time buckets in hours (decision-vintage and every-vintage views).
    lead_bucket_h: float = 6
    # Width of forecast-level bins in MW.
    level_bin_mw: float = 5000
    # Persistence baseline: actual this many hours before the slot.
    persistence_lag_h: int = 48
    # Uncertainty band: look back over this many finished calendar days ...
    band_window_days: int = 14
    # ... and call the band "full" only when at least this many of them have data.
    band_min_days: int = 7
    band_lo: float = 10
    band_hi: float = 90
