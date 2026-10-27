#!/usr/bin/env python
"""Diagnostic: does the assumed time alignment of WINDFOR hours to FUELHH half-hours fit the data?

For each shift k (in half-hours) compare the decision forecast for slot s with the actual at s + k slots, over every
January delivery day, and report MAE and bias. If the assumption (hourly forecast = the hour starting at startTime) is right,
the error should be smallest at k = 0. Also reports the hourly-mean alignment (forecast vs the mean of the two half-hours).

    python backend/scripts/alignment_check.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wind_analysis.config import AnalysisConfig  # noqa: E402
from wind_analysis.decision import decision_day  # noqa: E402
from wind_data.loader import load_snapshot  # noqa: E402

snap = load_snapshot(ROOT / "data" / "snapshot.json.gz")
cfg = AnalysisConfig()
days = [date(2026, 1, 2) + timedelta(i) for i in range(31)]
recs = [r for d in days for r in decision_day(snap, d, cfg).slots if r.forecast is not None and r.actual is not None]

print(f"{'shift (half-hours)':>20} {'shift (min)':>12} {'n':>6} {'MAE MW':>9} {'bias MW':>9}")
best = None
for k in range(-6, 7):
    errs = []
    for r in recs:
        a = snap.actual(r.slot + k * 1800)
        if a is not None:
            errs.append(r.forecast - a)
    mae = sum(abs(e) for e in errs) / len(errs)
    bias = sum(errs) / len(errs)
    best = min(best, (mae, k)) if best else (mae, k)
    print(f"{k:>20} {k * 30:>12} {len(errs):>6} {mae:>9.1f} {bias:>9.1f}")
print(f"\nsmallest MAE at shift {best[1]} half-hours ({best[1] * 30} min): {best[0]:.1f} MW")

# hourly-mean alignment: forecast for the hour vs the mean of the two half-hours
errs = []
for r in recs:
    if r.slot % 3600 == 0:
        a2 = snap.actual(r.slot + 1800)
        if a2 is not None:
            errs.append(r.forecast - (r.actual + a2) / 2)
print(f"hour-mean alignment (hour-start slots only): n={len(errs)} MAE {sum(abs(e) for e in errs)/len(errs):.1f} MW, "
      f"bias {sum(errs)/len(errs):.1f} MW")
