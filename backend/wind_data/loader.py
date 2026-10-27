"""Load snapshot.json.gz into an in-memory structure.

latest_forecast(target, cutoff) is a single bisect over that target's
publish times.
"""
from __future__ import annotations

import gzip
import json
from bisect import bisect_right
from pathlib import Path

SCHEMA = 1


class Snapshot:
    def __init__(self, meta: dict, actual_rows: list[list], forecast_rows: list[list]):
        self.meta = meta
        # actuals: start -> (mw, publish, settlement_date, period)
        self.actuals: dict[int, tuple] = {r[0]: (r[1], r[2], r[3], r[4]) for r in actual_rows}
        # forecasts: target start -> (sorted publish times, matching mw values)
        pubs: dict[int, list[int]] = {}
        vals: dict[int, list] = {}
        for publish, start, mw in sorted(forecast_rows):  # ascending publish
            pubs.setdefault(start, []).append(publish)
            vals.setdefault(start, []).append(mw)
        self._pubs = pubs
        self._vals = vals
        self.publish_times: list[int] = sorted({r[0] for r in forecast_rows})
        self.n_forecast_rows = len(forecast_rows)

    def latest_forecast(self, target: int, cutoff: int) -> tuple[int, float | None] | None:
        """Latest vintage for `target` with publish <= cutoff, as (publish, mw).

        None if no such vintage exists. If the latest vintage's value is null
        it is returned as (publish, None); it does not fall back to an older one.
        """
        pubs = self._pubs.get(target)
        if not pubs:
            return None
        i = bisect_right(pubs, cutoff)
        if i == 0:
            return None
        return pubs[i - 1], self._vals[target][i - 1]

    def vintages(self, target: int) -> list[tuple[int, float | None]]:
        """All (publish, mw) for a target, ascending publish."""
        return list(zip(self._pubs.get(target, []), self._vals.get(target, [])))

    def actual(self, start: int) -> float | None:
        a = self.actuals.get(start)
        return None if a is None else a[0]

    def actual_publish(self, start: int) -> int | None:
        """When the actual for this slot was published (None if there is no row)."""
        a = self.actuals.get(start)
        return None if a is None else a[1]


def load_snapshot(path: str | Path) -> Snapshot:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        d = json.load(fh)
    if d.get("schema") != SCHEMA:
        raise ValueError(f"unsupported snapshot schema {d.get('schema')!r}")
    return Snapshot(d["meta"], d["actuals"]["rows"], d["forecasts"]["rows"])
