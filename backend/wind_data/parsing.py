"""Parsers for raw Elexon BMRS rows (FUELHH wind actuals, WINDFOR forecasts).

Standard library only. Timestamps become integer epoch seconds (UTC).
Nulls are kept as None and never filled. Identical duplicate rows are dropped
and counted; conflicting duplicates raise DataConflict.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class DataConflict(Exception):
    """Two rows share a key but disagree on the value."""


class ParseError(Exception):
    """A row is not in the expected shape."""


@dataclass(frozen=True)
class Actual:
    start: int
    mw: float | None
    publish: int
    settlement_date: str
    period: int


@dataclass(frozen=True)
class Forecast:
    publish: int
    start: int
    mw: float | None


def parse_ts(value: str) -> int:
    """ISO-8601 UTC ('...Z') to epoch seconds. Rejects naive timestamps."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ParseError(f"timestamp without time zone: {value!r}")
    return int(dt.astimezone(timezone.utc).timestamp())


def to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mw(row: dict) -> float | None:
    v = row.get("generation")
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ParseError(f"non-numeric generation: {v!r}")
    return v


def parse_fuelhh(rows: list[dict]) -> tuple[list[Actual], int]:
    """Return (actuals sorted by start, identical duplicates dropped)."""
    out: dict[int, Actual] = {}
    dups = 0
    for r in rows:
        try:
            if r["dataset"] != "FUELHH" or r["fuelType"] != "WIND":
                raise ParseError(f"unexpected dataset/fuelType: {r['dataset']}/{r['fuelType']}")
            a = Actual(parse_ts(r["startTime"]), _mw(r), parse_ts(r["publishTime"]),
                       r["settlementDate"], int(r["settlementPeriod"]))
        except KeyError as e:
            raise ParseError(f"missing field {e} in {r!r}") from e
        prev = out.get(a.start)
        if prev is None:
            out[a.start] = a
        elif prev == a:
            dups += 1
        else:
            raise DataConflict(f"FUELHH conflict at {to_iso(a.start)}: {prev} vs {a}")
    return sorted(out.values(), key=lambda a: a.start), dups


def parse_windfor(rows: list[dict]) -> tuple[list[Forecast], int]:
    """Return (forecasts sorted by (publish, start), identical duplicates dropped)."""
    out: dict[tuple[int, int], Forecast] = {}
    dups = 0
    for r in rows:
        try:
            if r["dataset"] != "WINDFOR":
                raise ParseError(f"unexpected dataset: {r['dataset']}")
            f = Forecast(parse_ts(r["publishTime"]), parse_ts(r["startTime"]), _mw(r))
        except KeyError as e:
            raise ParseError(f"missing field {e} in {r!r}") from e
        key = (f.publish, f.start)
        prev = out.get(key)
        if prev is None:
            out[key] = f
        elif prev == f:
            dups += 1
        else:
            raise DataConflict(f"WINDFOR conflict at {key}: {prev} vs {f}")
    return sorted(out.values(), key=lambda f: (f.publish, f.start)), dups
