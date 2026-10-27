#!/usr/bin/env python
"""Regenerate every number quoted in README.md, docs/PITCH.md and docs/DESIGN.md.

    python backend/scripts/doc_numbers.py            # prints JSON
    python backend/scripts/doc_numbers.py --compare https://YOUR-PROJECT.vercel.app   # also diff against a live URL

It calls the same app.py that Vercel runs, in-process, against the committed snapshot, so the figures are the API's own.
The "volume lens" block is NOT shown on any screen: it is calculated here from /api/series (see docs/PITCH.md).
Needs backend/requirements-dev.txt (httpx).
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.pop("STATIC_DIR", None)
os.environ.pop("SNAPSHOT_PATH", None)

from starlette.testclient import TestClient  # noqa: E402

import app as entry  # noqa: E402

SLOT_H = 0.5
DEMO_DAYS = {  # decision date -> why it is in the demo
    "2026-01-14": "worked example",
    "2026-01-27": "worst over-forecast day (delivery 28 Jan)",
    "2026-01-18": "only clear under-forecast day (delivery 19 Jan)",
    "2026-01-04": "closest to zero average error (delivery 5 Jan)",
    "2026-01-01": "first day, no range (delivery 2 Jan)",
}
CUTOFF_SWEEP = ("03:00", "05:00", "08:00", "09:20", "09:50", "12:00", "16:00")


def gather(c: TestClient) -> dict:
    out: dict = {}
    t = time.perf_counter(); meta = c.get("/api/meta").json(); out["seconds_meta_first_call"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter(); acc = c.get("/api/accuracy").json(); out["seconds_accuracy_first_call"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter(); ser = c.get("/api/series").json(); out["seconds_series_first_call"] = round(time.perf_counter() - t, 3)
    out["series_response_bytes"] = len(c.get("/api/series").content)
    out["snapshot"] = {k: meta["data"][k] for k in ("fetched_at", "n_actual_rows", "n_forecast_rows", "n_publish_times", "sha256")}
    out["decision_window"] = meta["decision_window"]

    o = acc["overall"]
    out["overall"] = {k: o[k] for k in ("n", "mae", "rmse", "bias", "wape", "share_over", "share_under", "shortfall_90")}
    out["abs_percentiles"] = o["abs_pct"]
    out["signed_percentiles"] = o["signed_pct"]
    out["counts"] = acc["counts"]
    p = acc["persistence"]
    out["persistence"] = {"n_paired": p["n_paired"], "n_missing_baseline": p["n_missing_baseline"],
                          "forecast_mae": p["forecast"]["mae"], "baseline_mae": p["baseline"]["mae"],
                          "forecast_rmse": p["forecast"]["rmse"], "baseline_rmse": p["baseline"]["rmse"],
                          "skill_mae": p["skill_mae"], "skill_rmse": p["skill_rmse"], "baseline_bias": p["baseline"]["bias"]}
    out["by_level"] = [{k: r[k] for k in ("lo", "hi", "n", "bias", "mae", "share_over")} for r in acc["by_level"]]
    out["by_lead_decision_vintage"] = [{k: r[k] for k in ("lo", "hi", "n", "mae", "bias")} for r in acc["by_lead"]]
    out["by_lead_every_vintage"] = [{k: r[k] for k in ("lo", "hi", "n", "mae", "bias")} for r in acc["lead_all_vintages"]]
    out["by_hour"] = [{"hour": r["key"], "mae": r["mae"], "bias": r["bias"]} for r in acc["by_hour"]]
    days = acc["by_day"]
    out["by_day"] = {
        "n_days": len(days),
        "days_over_forecast": sum(1 for d in days if d["bias"] > 0),
        "days_under_forecast": sum(1 for d in days if d["bias"] < 0),
        "worst_over": max(((d["key"], d["bias"]) for d in days), key=lambda x: x[1]),
        "worst_under": min(((d["key"], d["bias"]) for d in days), key=lambda x: x[1]),
        "closest_to_zero": min(((d["key"], d["bias"]) for d in days), key=lambda x: abs(x[1])),
        "daily_mae_min_max": (min(d["mae"] for d in days), max(d["mae"] for d in days)),
    }

    # --- calibration of the likely range, over every half-hour that had one
    out["band_methods"] = dict(Counter(d["band_method"] for d in ser["days"]))
    inside = below = above = n = 0
    for pt in ser["points"]:
        if pt["actual_mw"] is None or pt["band_low_mw"] is None:
            continue
        n += 1
        if pt["actual_mw"] < pt["band_low_mw"]:
            below += 1
        elif pt["actual_mw"] > pt["band_high_mw"]:
            above += 1
        else:
            inside += 1
    out["band_calibration"] = {"n": n, "inside": inside, "below": below, "above": above,
                               "inside_pct": round(100 * inside / n, 1), "below_pct": round(100 * below / n, 1),
                               "above_pct": round(100 * above / n, 1)}

    # --- volume lens: MWh, no prices. "short" = wind the plan counted on that did not arrive; "surplus" = wind beyond the plan.
    by_date: dict = {}
    for pt in ser["points"]:
        by_date.setdefault(pt["decision_date"], []).append(pt)
    rows = []
    for d, pts in by_date.items():
        pts = [x for x in pts if None not in (x["forecast_mw"], x["actual_mw"], x["band_low_mw"])]
        if len(pts) not in (46, 48, 50):
            continue
        low = [max(0.0, x["band_low_mw"]) for x in pts]
        f = [x["forecast_mw"] for x in pts]
        a = [x["actual_mw"] for x in pts]
        rows.append({
            "F": sum(f) * SLOT_H, "A": sum(a) * SLOT_H, "L": sum(low) * SLOT_H,
            "short_exp": sum(max(0, fi - ai) for fi, ai in zip(f, a)) * SLOT_H,
            "surp_exp": sum(max(0, ai - fi) for fi, ai in zip(f, a)) * SLOT_H,
            "short_cau": sum(max(0, li - ai) for li, ai in zip(low, a)) * SLOT_H,
            "surp_cau": sum(max(0, ai - li) for li, ai in zip(low, a)) * SLOT_H,
        })
    mean = lambda k: round(st.mean(r[k] for r in rows))  # noqa: E731
    out["volume_lens_MWh_per_day"] = {
        "days_with_a_range": len(rows),
        "mean_expected": mean("F"), "mean_actual": mean("A"),
        "mean_extra_to_cover": round(st.mean(r["F"] - r["L"] for r in rows)),
        "extra_to_cover_min": round(min(r["F"] - r["L"] for r in rows)),
        "extra_to_cover_max": round(max(r["F"] - r["L"] for r in rows)),
        "extra_as_share_of_expected": round(st.mean(r["F"] - r["L"] for r in rows) / st.mean(r["F"] for r in rows), 3),
        "plan_on_expected": {"short": mean("short_exp"), "surplus": mean("surp_exp")},
        "plan_on_cautious": {"short": mean("short_cau"), "surplus": mean("surp_cau")},
        "days_daily_actual_below_expected": sum(1 for r in rows if r["A"] < r["F"]),
        "days_daily_actual_below_cautious": sum(1 for r in rows if r["A"] < r["L"]),
    }

    # --- cut-off sensitivity (a 12:00 or 16:00 cut-off is after gate closure: contrast only)
    sweep = {}
    for cut in CUTOFF_SWEEP:
        r = c.get("/api/accuracy", params={"cutoff": cut}).json()["overall"]
        sweep[cut] = {"mae": r["mae"], "bias": r["bias"], "share_over": r["share_over"]}
    out["cutoff_sweep"] = sweep

    # --- demo days
    demo = {}
    day_rows = {r["key"]: r for r in days}
    for decision_date, why in DEMO_DAYS.items():
        d = c.get("/api/decision", params={"decision_date": decision_date}).json()
        sl = d["slots"]
        f = [s["forecast_mw"] for s in sl]; a = [s["actual_mw"] for s in sl]
        lo = [s["band_low_mw"] for s in sl]; hi = [s["band_high_mw"] for s in sl]
        has = lo[0] is not None
        demo[decision_date] = {
            "why": why, "delivery": d["delivery_date"], "vintage": d["vintages"], "band_method": d["band"]["method"],
            "band_days": d["band"]["n_days"], "expected_mean_MW": st.mean(f), "expected_MWh": sum(f) * SLOT_H,
            "actual_mean_MW": st.mean(a), "actual_MWh": sum(a) * SLOT_H,
            "cautious_mean_MW": st.mean(lo) if has else None,
            "extra_MWh": (sum(f) - sum(lo)) * SLOT_H if has else None,
            "half_hours_inside_range": sum(1 for ai, l, h in zip(a, lo, hi) if l is not None and l <= ai <= h) if has else None,
            "day_bias": day_rows[d["delivery_date"]]["bias"], "day_mae": day_rows[d["delivery_date"]]["mae"],
        }
    out["demo_days"] = demo
    return out


def fetch_json(base: str, path: str):
    with urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + path, headers={"User-Agent": "doc-numbers/1.0"}), timeout=60) as r:
        return json.load(r)


def main() -> int:
    numbers = gather(TestClient(entry.app))
    if "--compare" in sys.argv:
        base = sys.argv[sys.argv.index("--compare") + 1]
        live = fetch_json(base, "/api/accuracy")["overall"]
        local = numbers["overall"]
        numbers["live_vs_local_overall"] = {k: {"local": local[k], "live": live[k], "equal": abs(local[k] - live[k]) < 1e-9} for k in local}
    print(json.dumps(numbers, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
