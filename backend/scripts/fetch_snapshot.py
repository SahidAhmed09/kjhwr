#!/usr/bin/env python
"""Download wind actuals (FUELHH) and every WINDFOR vintage for the window and
write backend/data/snapshot.json.gz. Standard library only.

    python backend/scripts/fetch_snapshot.py [--publish-from 2026-01-01 --publish-to 2026-02-01
                                              --settlement-from 2026-01-02 --settlement-to 2026-02-01]

publish window is [from 00:00Z, to 00:00Z); settlement dates are inclusive.
Nothing is estimated or filled: missing/null values stay missing/null.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wind_data.loader import SCHEMA, load_snapshot  # noqa: E402
from wind_data.parsing import parse_fuelhh, parse_windfor, parse_ts  # noqa: E402
from wind_data.report import build_report  # noqa: E402

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
RETRIES = 5
TIMEOUT = 90


def get_json(url: str, log: list[dict]) -> list[dict]:
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "wind-snapshot/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read())
            if not isinstance(data, list):
                raise ValueError(f"expected a JSON list, got {type(data).__name__}")
            log.append({"url": url, "rows": len(data), "attempts": attempt})
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (408, 429, 500, 502, 503, 504):
                raise  # a 4xx like 400/404 will not fix itself
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
        wait = 2 ** attempt
        print(f"  retry {attempt}/{RETRIES} in {wait}s after {last!r}", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last!r}")


def day(s: str) -> date:
    return date.fromisoformat(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-from", default="2026-01-01")
    ap.add_argument("--publish-to", default="2026-02-01")
    ap.add_argument("--settlement-from", default="2026-01-02")
    ap.add_argument("--settlement-to", default="2026-02-01")
    ap.add_argument("--out", default=str(ROOT / "data" / "snapshot.json.gz"))
    a = ap.parse_args()

    log: list[dict] = []
    raw_wf: list[dict] = []
    d, end = day(a.publish_from), day(a.publish_to)
    while d < end:  # one request per UTC day of publishTime
        nxt = d + timedelta(days=1)
        q = urllib.parse.urlencode({"publishDateTimeFrom": f"{d}T00:00:00Z",
                                    "publishDateTimeTo": f"{nxt}T00:00:00Z"})
        print(f"WINDFOR publish {d}")
        raw_wf += get_json(f"{BASE}/datasets/WINDFOR/stream?{q}", log)
        d = nxt

    raw_fh: list[dict] = []
    d, end = day(a.settlement_from), day(a.settlement_to)
    while d <= end:  # 7 settlement days per request
        to = min(d + timedelta(days=6), end)
        q = urllib.parse.urlencode({"settlementDateFrom": d.isoformat(),
                                    "settlementDateTo": to.isoformat(), "fuelType": "WIND"})
        print(f"FUELHH settlement {d}..{to}")
        raw_fh += get_json(f"{BASE}/datasets/FUELHH/stream?{q}", log)
        d = to + timedelta(days=1)

    actuals, fh_dups = parse_fuelhh(raw_fh)
    forecasts, wf_dups = parse_windfor(raw_wf)

    # Keep only what is in the agreed window; report anything outside.
    p_lo = parse_ts(f"{a.publish_from}T00:00:00Z")
    p_hi = parse_ts(f"{a.publish_to}T00:00:00Z")
    out_fc = [f for f in forecasts if not p_lo <= f.publish < p_hi]
    forecasts = [f for f in forecasts if p_lo <= f.publish < p_hi]
    out_ac = [x for x in actuals if not a.settlement_from <= x.settlement_date <= a.settlement_to]
    actuals = [x for x in actuals if a.settlement_from <= x.settlement_date <= a.settlement_to]
    if out_fc or out_ac:
        print(f"dropped outside window: {len(out_fc)} forecast rows, {len(out_ac)} actual rows")

    snap = {
        "schema": SCHEMA,
        "meta": {
            "base_url": BASE,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_zone": "UTC; all times are epoch seconds",
            "window": {"publish_from": f"{a.publish_from}T00:00:00Z", "publish_to": f"{a.publish_to}T00:00:00Z",
                       "settlement_from": a.settlement_from, "settlement_to": a.settlement_to},
            "duplicates": {"fuelhh": fh_dups, "windfor": wf_dups},
            "dropped_outside_window": {"windfor": len(out_fc), "fuelhh": len(out_ac)},
            "requests": log,
        },
        "actuals": {"cols": ["start", "mw", "publish", "settlement_date", "period"],
                    "rows": [[x.start, x.mw, x.publish, x.settlement_date, x.period] for x in actuals]},
        "forecasts": {"cols": ["publish", "start", "mw"],
                      "rows": [[f.publish, f.start, f.mw] for f in forecasts]},
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write(json.dumps(snap, separators=(",", ":")).encode("utf-8"))
    tmp.replace(out)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (out.parent / "snapshot.sha256").write_text(f"{digest}  {out.name}\n")

    report = build_report(load_snapshot(out))
    (out.parent / "REPORT.txt").write_text(report + f"\n\nsnapshot sha256: {digest}\n", encoding="utf-8")
    print()
    print(report)
    print(f"\nwrote {out} ({out.stat().st_size} bytes) sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
