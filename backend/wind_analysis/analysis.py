"""Accuracy evaluation of the decision forecast: overall, breakdowns, every-vintage
lead view and persistence baseline. Pure Python, no I/O."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import floor

from .config import AnalysisConfig
from .decision import decision_day
from .metrics import error_metrics
from .timeutil import hour_floor, london_hour


def _num(x: float):
    return int(x) if x == int(x) else x


def _bucket(x: float, width: float):
    return _num(floor(x / width) * width)


def _grouped(pairs, key_fn, extra=None) -> list[dict]:
    """pairs: iterable of (error, actual, ctx). Returns metric rows sorted by key."""
    g: dict = defaultdict(lambda: ([], []))
    for e, a, ctx in pairs:
        k = key_fn(ctx)
        g[k][0].append(e)
        g[k][1].append(a)
    return [{"key": k, **error_metrics(*g[k])} for k in sorted(g)]


def _with_range(rows: list[dict], width: float) -> list[dict]:
    for r in rows:
        r["lo"], r["hi"] = r["key"], _num(r["key"] + width)
    return rows


def evaluate(src, days: list[date], cfg: AnalysisConfig = AnalysisConfig()) -> dict:
    decisions = [decision_day(src, d, cfg) for d in days]

    counts = {
        "n_days": len(decisions),
        "n_slots": sum(x.n_slots for x in decisions),
        "n_missing_forecast": sum(x.n_missing_forecast for x in decisions),
        "n_missing_actual": sum(x.n_missing_actual for x in decisions),
        "n_missing_both": sum(x.n_missing_both for x in decisions),
        "n_scored": sum(x.n_scored for x in decisions),
    }

    scored = [(x, r) for x in decisions for r in x.slots if r.error is not None]
    pairs = [(r.error, r.actual, (x, r)) for x, r in scored]

    by_day = []
    for x in decisions:
        es = [r.error for r in x.slots if r.error is not None]
        ac = [r.actual for r in x.slots if r.error is not None]
        by_day.append({"key": x.day.isoformat(), **error_metrics(es, ac),
                       "n_slots": x.n_slots, "n_missing_forecast": x.n_missing_forecast,
                       "n_missing_actual": x.n_missing_actual})

    # --- every vintage (ex-post view of how accuracy depends on lead time)
    all_pairs = []
    for x in decisions:
        for r in x.slots:
            if r.actual is None:
                continue
            for pub, mw in src.vintages(hour_floor(r.slot)):
                if mw is not None:
                    all_pairs.append((mw - r.actual, r.actual, (r.slot - pub) / 3600))

    return {
        "config": {"cutoff_time": cfg.cutoff_time.strftime("%H:%M"), "tz": "Europe/London",
                   "error": "forecast - actual", "lead_bucket_h": cfg.lead_bucket_h,
                   "level_bin_mw": cfg.level_bin_mw},
        "counts": counts,
        "overall": error_metrics([p[0] for p in pairs], [p[1] for p in pairs]),
        "by_day": by_day,
        "by_hour": _grouped(pairs, lambda c: london_hour(c[1].slot)),
        "by_lead": _with_range(_grouped(pairs, lambda c: _bucket(c[1].lead_h, cfg.lead_bucket_h)),
                               cfg.lead_bucket_h),
        "by_level": _with_range(_grouped(pairs, lambda c: _bucket(c[1].forecast, cfg.level_bin_mw)),
                                cfg.level_bin_mw),
        "lead_all_vintages": _with_range(_grouped(all_pairs, lambda lead: _bucket(lead, cfg.lead_bucket_h)),
                                         cfg.lead_bucket_h),
        "persistence": _persistence(src, scored, cfg),
    }


def persistence_forecast(src, slot: int, cutoff: int, lag_h: int) -> float | None:
    """Actual `lag_h` hours before `slot`, only if it had been published by the cut-off."""
    s = slot - lag_h * 3600
    a, pub = src.actual(s), src.actual_publish(s)
    if a is None or pub is None or pub > cutoff:
        return None
    return a


def _persistence(src, scored, cfg: AnalysisConfig) -> dict:
    fe, be, act = [], [], []
    missing = 0
    for x, r in scored:
        b = persistence_forecast(src, r.slot, x.cutoff, cfg.persistence_lag_h)
        if b is None:
            missing += 1
            continue
        fe.append(r.error)
        be.append(b - r.actual)
        act.append(r.actual)
    fm, bm = error_metrics(fe, act), error_metrics(be, act)

    def skill(k):
        return None if not bm[k] else 1 - fm[k] / bm[k]

    return {"baseline_name": f"actual {cfg.persistence_lag_h} h earlier", "n_paired": len(fe),
            "n_missing_baseline": missing, "forecast": fm, "baseline": bm,
            "skill_mae": skill("mae") if fe else None, "skill_rmse": skill("rmse") if fe else None}
