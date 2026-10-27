"""Error metrics. error = forecast - actual (positive = over-forecast)."""
from __future__ import annotations

import math

ABS_PCTS = (50, 90, 95, 99)
SIGNED_PCTS = (5, 10, 25, 50, 75, 90, 95)


def percentile(sorted_vals: list[float], p: float) -> float | None:
    """Linear-interpolation percentile (same as numpy's default) of an ascending list."""
    if not sorted_vals:
        return None
    pos = (len(sorted_vals) - 1) * p / 100
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (pos - lo) * (sorted_vals[hi] - sorted_vals[lo])


def error_metrics(errors: list[float], actuals: list[float]) -> dict:
    """Metrics for paired errors/actuals. Empty input gives None values, never zeros.

    shortfall_90 = max(0, P90 of signed error): the MW by which the forecast
    exceeded the actual on the worst 10% of slots, i.e. the extra cover needed
    to be short on at most 10% of slots.
    """
    if len(errors) != len(actuals):
        raise ValueError("errors and actuals must have the same length")
    n = len(errors)
    if n == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "wape": None,
                "abs_pct": {f"p{p}": None for p in ABS_PCTS},
                "signed_pct": {f"p{p}": None for p in SIGNED_PCTS},
                "share_over": None, "share_under": None, "share_exact": None,
                "shortfall_90": None}
    abs_e = sorted(abs(e) for e in errors)
    signed = sorted(errors)
    sum_abs = sum(abs_e)
    sum_act = sum(actuals)
    p90 = percentile(signed, 90)
    return {
        "n": n,
        "mae": sum_abs / n,
        "rmse": math.sqrt(sum(e * e for e in errors) / n),
        "bias": sum(errors) / n,
        "wape": sum_abs / sum_act if sum_act else None,
        "abs_pct": {f"p{p}": percentile(abs_e, p) for p in ABS_PCTS},
        "signed_pct": {f"p{p}": percentile(signed, p) for p in SIGNED_PCTS},
        "share_over": sum(1 for e in errors if e > 0) / n,
        "share_under": sum(1 for e in errors if e < 0) / n,
        "share_exact": sum(1 for e in errors if e == 0) / n,
        "shortfall_90": max(0.0, p90),
    }
