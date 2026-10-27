"""Data-quality report computed from a snapshot (read-only; fills nothing)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from .loader import Snapshot
from .parsing import to_iso


def build_report(s: Snapshot) -> str:
    m = s.meta
    L: list[str] = []
    add = L.append
    add("DATA REPORT")
    add(f"fetched_at (UTC): {m['fetched_at']}   base: {m['base_url']}")
    w = m["window"]
    add(f"window: publishTime [{w['publish_from']}, {w['publish_to']})  "
        f"settlementDate {w['settlement_from']}..{w['settlement_to']} inclusive")
    add("")

    # --- actuals (FUELHH WIND)
    acts = sorted(s.actuals.items())
    add(f"ACTUALS (FUELHH WIND): {len(acts)} rows after de-duplication")
    add(f"  identical duplicates dropped: {m['duplicates']['fuelhh']}; conflicting duplicates: 0 (any conflict aborts the build)")
    nulls = sum(1 for _, a in acts if a[0] is None)
    negs = sum(1 for _, a in acts if a[0] is not None and a[0] < 0)
    vals = [a[0] for _, a in acts if a[0] is not None]
    add(f"  null generation: {nulls}; negative generation: {negs}; min/max MW: {min(vals)}/{max(vals)}")
    by_day: dict[str, int] = defaultdict(int)
    for _, a in acts:
        by_day[a[2]] += 1
    d0, d1 = date.fromisoformat(w["settlement_from"]), date.fromisoformat(w["settlement_to"])
    days = [(d0 + timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)]
    missing = {d: 48 - by_day.get(d, 0) for d in days if by_day.get(d, 0) != 48}
    extra = sorted(d for d in by_day if d not in days)
    add(f"  settlement days expected: {len(days)}; days with != 48 half-hours: {len(missing)}")
    for d, n in missing.items():
        add(f"    {d}: {n:+d} missing" if n > 0 else f"    {d}: {-n} surplus")
    if extra:
        add(f"  rows on days outside the window: {extra}")
    periods_bad = [st for st, a in acts if not 1 <= a[3] <= 50]
    add(f"  settlement periods outside 1..50: {len(periods_bad)}")
    add("")

    # --- forecasts (WINDFOR)
    pubs = s.publish_times
    n_rows = sum(len(v) for v in s._pubs.values())
    add(f"FORECASTS (WINDFOR): {n_rows} rows after de-duplication")
    add(f"  identical duplicates dropped: {m['duplicates']['windfor']}; conflicting duplicates: 0")
    fn = sum(1 for v in s._vals.values() for x in v if x is None)
    fneg = sum(1 for v in s._vals.values() for x in v if x is not None and x < 0)
    fv = [x for v in s._vals.values() for x in v if x is not None]
    add(f"  null generation: {fn}; negative generation: {fneg}; min/max MW: {min(fv)}/{max(fv)}")
    add(f"  distinct publish times: {len(pubs)}  ({to_iso(pubs[0])} .. {to_iso(pubs[-1])})")
    tod = Counter(to_iso(p)[11:16] for p in pubs)
    add("  publish time-of-day (UTC) counts: " + ", ".join(f"{k}x{v}" for k, v in sorted(tod.items())))
    gaps = Counter(round((b - a) / 3600, 2) for a, b in zip(pubs, pubs[1:]))
    add("  gaps between consecutive publishes (hours): " + ", ".join(f"{k}x{v}" for k, v in sorted(gaps.items())))
    per_day = Counter(to_iso(p)[:10] for p in pubs)
    odd = {d: n for d, n in per_day.items() if n != 8}
    add(f"  publishes per UTC day: {dict(Counter(per_day.values()))}; days != 8: {odd or 'none'}")
    rows_per_pub = Counter()
    pub_rows: Counter = Counter()
    hz = []
    for start, plist in s._pubs.items():
        for p in plist:
            pub_rows[p] += 1
            hz.append((start - p) / 3600)
    rows_per_pub.update(pub_rows.values())
    add(f"  rows per publish: {dict(rows_per_pub)}")
    add(f"  horizon (startTime - publishTime) hours: min {min(hz)}, max {max(hz)}; "
        f"negative-horizon rows: {sum(1 for h in hz if h < 0)}")
    odd_min = Counter(to_iso(st)[14:16] for st in s._pubs)
    add(f"  forecast startTime minute-of-hour: {dict(odd_min)}")
    add("")

    # --- cross-check
    add("COVERAGE CHECK")
    covered = sum(1 for st in s.actuals if s.actual(st) is not None)
    hours = sorted(st for st in s._pubs if st % 3600 == 0)
    with_act = sum(1 for st in hours if st in s.actuals and (st + 1800) in s.actuals)
    add(f"  forecast target hours: {len(hours)}; of which both half-hour actuals present: {with_act}")
    return "\n".join(L)
