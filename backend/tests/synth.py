"""SYNTHETIC data builders. Used only by unit tests; never loaded by the app."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wind_analysis.timeutil import market_day_slots  # noqa: E402
from wind_data.loader import Snapshot  # noqa: E402
from wind_data.parsing import parse_ts  # noqa: E402


def ts(s: str) -> int:
    return parse_ts(s)


def hours_of(slots: list[int]) -> list[int]:
    return sorted({s - s % 3600 for s in slots})


def build(actuals: dict, forecasts: list) -> Snapshot:
    """actuals: {start: mw | (mw, publish)}; forecasts: [(publish, hour_start, mw)]."""
    rows = []
    for s, v in sorted(actuals.items()):
        mw, pub = v if isinstance(v, tuple) else (v, s + 1800)  # FUELHH publish = start + 30 min
        rows.append([s, mw, pub, "synthetic", 0])
    return Snapshot({}, rows, [list(f) for f in forecasts])


def day_data(d: date, actual_mw, forecast_mw, publish: int):
    """Full day: one actual per slot, one vintage (at `publish`) per hour.
    actual_mw(slot_start) and forecast_mw(hour_start) are callables or constants."""
    a = actual_mw if callable(actual_mw) else (lambda s: actual_mw)
    f = forecast_mw if callable(forecast_mw) else (lambda h: forecast_mw)
    slots = market_day_slots(d)
    return ({s: a(s) for s in slots}, [(publish, h, f(h)) for h in hours_of(slots)])


def merge(*parts):
    acts, fcs = {}, []
    for a, f in parts:
        acts.update(a)
        fcs += f
    return acts, fcs


def write_snapshot(path, actuals: dict, forecasts: list, settlement_from: str, settlement_to: str,
                   schema: int = 1) -> None:
    """Write a SYNTHETIC snapshot file in the real on-disk format (tests only)."""
    import gzip
    import json
    snap = build(actuals, forecasts)
    doc = {
        "schema": schema,
        "meta": {"base_url": "synthetic://test", "fetched_at": "2026-01-01T00:00:00Z",
                 "window": {"publish_from": "2026-01-01T00:00:00Z", "publish_to": "2026-02-01T00:00:00Z",
                            "settlement_from": settlement_from, "settlement_to": settlement_to}},
        "actuals": {"cols": [], "rows": [[s, a[0], a[1], a[2], a[3]] for s, a in sorted(snap.actuals.items())]},
        "forecasts": {"cols": [], "rows": [list(f) for f in forecasts]},
    }
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(doc, fh)
