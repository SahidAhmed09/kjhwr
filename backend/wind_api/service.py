"""Lazy data loading and per-cut-off result caching over the analysis module."""
from __future__ import annotations

import gzip
import hashlib
import json
import threading
from collections import Counter, OrderedDict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from wind_analysis.analysis import evaluate
from wind_analysis.band import uncertainty_band
from wind_analysis.config import AnalysisConfig
from wind_analysis.decision import decision_day
from wind_analysis.timeutil import LONDON
from wind_data.loader import Snapshot, load_snapshot
from wind_data.parsing import to_iso

from .models import (AccuracyResponse, BandInfo, CutoffInfo, DataInfo, DecisionResponse, DecisionWindow,
                     Defaults, MetaResponse, SeriesDay, SeriesPoint, SeriesResponse, ServiceInfo, SlotOut,
                     VintageUse)

VERSION = "0.1.0"
DEFAULT_CUTOFF = "09:20"
CACHE_SIZE = 64

NOTES = [
    "Data is a committed January 2026 snapshot of Elexon FUELHH (wind actuals) and WINDFOR (wind forecasts), "
    "not live data.",
    "Generation is treated as MW. The WINDFOR unit is not stated in the Elexon API documentation and has not been "
    "verified.",
    "WINDFOR is hourly; each hourly forecast is applied to both half-hour slots of that hour and compared with the "
    "half-hourly FUELHH actual.",
    "A forecast is treated as available from its publishTime. The real delay between publishTime and availability "
    "to a user is unknown.",
    "The snapshot starts on 1 Jan 2026, so the error history behind the uncertainty band is short in early January "
    "(see band.method).",
]


class DataUnavailable(Exception):
    """The snapshot is missing or unreadable (HTTP 503)."""


class OutsideWindow(Exception):
    def __init__(self, first: date, last: date):
        super().__init__(f"decision_date is outside the data window: use {first} to {last}")
        self.first, self.last = first, last


class _Cache:
    def __init__(self, size: int = CACHE_SIZE):
        self._d: OrderedDict = OrderedDict()
        self._size = size

    def get(self, key):
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def put(self, key, value):
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self._size:
            self._d.popitem(last=False)


def cfg_for(cutoff: str) -> AnalysisConfig:
    h, m = cutoff.split(":")
    return AnalysisConfig(cutoff_time=time(int(h), int(m)))


class AnalysisService:
    def __init__(self, snapshot_path: Path):
        self.path = Path(snapshot_path)
        self._snap: Snapshot | None = None
        self._sha = ""
        self._lock = threading.RLock()
        self._accuracy = _Cache()
        self._decisions = _Cache()
        self._series = _Cache()

    # --- state
    @property
    def data_file_present(self) -> bool:
        return self.path.is_file()

    @property
    def data_loaded(self) -> bool:
        return self._snap is not None

    def snapshot(self) -> Snapshot:
        """Load on first use. A failed load is not remembered, so data that appears later is picked up."""
        with self._lock:
            if self._snap is not None:
                return self._snap
            fix = "Generate it with: python backend/scripts/fetch_snapshot.py"
            try:
                raw = self.path.read_bytes()
            except FileNotFoundError:
                raise DataUnavailable(f"Data snapshot not found ({self.path.name}). {fix}") from None
            except OSError as e:
                raise DataUnavailable(f"Data snapshot cannot be read ({self.path.name}): {e}. {fix}") from None
            try:
                snap = load_snapshot(self.path)
                snap.meta["window"]["settlement_from"], snap.meta["window"]["settlement_to"]
            except (OSError, EOFError, ValueError, KeyError, TypeError, json.JSONDecodeError, gzip.BadGzipFile) as e:
                raise DataUnavailable(
                    f"Data snapshot is unreadable or invalid ({self.path.name}: {type(e).__name__}: {e}). {fix}"
                ) from None
            self._sha = hashlib.sha256(raw).hexdigest()
            self._snap = snap
            return snap

    def _window(self, snap: Snapshot) -> tuple[date, date]:
        w = snap.meta["window"]
        return date.fromisoformat(w["settlement_from"]), date.fromisoformat(w["settlement_to"])

    # --- endpoints
    def meta(self) -> MetaResponse:
        snap = self.snapshot()
        w = snap.meta["window"]
        first, last = self._window(snap)
        return MetaResponse(
            service=ServiceInfo(name="wind-forecast-api", version=VERSION),
            data=DataInfo(fetched_at=snap.meta.get("fetched_at", ""), base_url=snap.meta.get("base_url", ""),
                          publish_from=w["publish_from"], publish_to=w["publish_to"],
                          settlement_from=first, settlement_to=last,
                          n_actual_rows=len(snap.actuals), n_forecast_rows=snap.n_forecast_rows,
                          n_publish_times=len(snap.publish_times), sha256=self._sha),
            decision_window=DecisionWindow(first=first - timedelta(days=1), last=last - timedelta(days=1)),
            defaults=Defaults(cutoff=DEFAULT_CUTOFF, timezone="Europe/London", error_definition="forecast - actual"),
            notes=NOTES,
        )

    def decision(self, decision_date: date, cutoff: str) -> DecisionResponse:
        snap = self.snapshot()
        first, last = self._window(snap)
        lo, hi = first - timedelta(days=1), last - timedelta(days=1)
        if not lo <= decision_date <= hi:
            raise OutsideWindow(lo, hi)
        key = (decision_date, cutoff)
        with self._lock:
            hit = self._decisions.get(key)
            if hit is None:
                hit = self._decision(snap, decision_date, cutoff)
                self._decisions.put(key, hit)
            return hit

    def _decision(self, snap: Snapshot, decision_date: date, cutoff: str) -> DecisionResponse:
        cfg = cfg_for(cutoff)
        delivery = decision_date + timedelta(days=1)
        day = decision_day(snap, delivery, cfg)
        band = uncertainty_band(snap, delivery, cfg)
        slots = []
        for r in day.slots:
            iv = band.interval(r.forecast) if r.forecast is not None else None
            slots.append(SlotOut(
                start_utc=to_iso(r.slot), start_local=datetime.fromtimestamp(r.slot, tz=LONDON).isoformat(),
                forecast_mw=r.forecast, actual_mw=r.actual,
                vintage_publish_utc=None if r.vintage_publish is None else to_iso(r.vintage_publish),
                lead_h=r.lead_h, band_low_mw=None if iv is None else iv[0], band_high_mw=None if iv is None else iv[1]))
        used = Counter(r.vintage_publish for r in day.slots if r.forecast is not None)
        return DecisionResponse(
            decision_date=decision_date, delivery_date=delivery,
            cutoff=CutoffInfo(local=cutoff, utc=to_iso(day.cutoff), timezone="Europe/London"),
            n_slots=day.n_slots, n_missing_forecast=day.n_missing_forecast,
            n_missing_actual=day.n_missing_actual, n_scored=day.n_scored,
            band=BandInfo(method=band.method, label=band.label, n_days=band.n_days, n_errors=band.n_errors,
                          p10=band.p10, p90=band.p90),
            vintages=[VintageUse(publish_utc=to_iso(p), n_slots=n) for p, n in sorted(used.items())],
            slots=slots)

    def accuracy(self, cutoff: str) -> AccuracyResponse:
        snap = self.snapshot()
        with self._lock:
            hit = self._accuracy.get(cutoff)
            if hit is None:
                first, last = self._window(snap)
                days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
                res = evaluate(snap, days, cfg_for(cutoff))
                hit = AccuracyResponse(cutoff_local=cutoff, **res)
                self._accuracy.put(cutoff, hit)
            return hit

    def series(self, cutoff: str) -> SeriesResponse:
        """Every decision day's forecast, actual and band, flattened in time order."""
        snap = self.snapshot()
        with self._lock:
            hit = self._series.get(cutoff)
            if hit is None:
                first, last = self._window(snap)
                days, points = [], []
                for i in range((last - first).days + 1):
                    delivery = first + timedelta(days=i)
                    d = self.decision(delivery - timedelta(days=1), cutoff)
                    days.append(SeriesDay(decision_date=d.decision_date, delivery_date=d.delivery_date,
                                          band_method=d.band.method))
                    points += [SeriesPoint(start_utc=s.start_utc, decision_date=d.decision_date,
                                           forecast_mw=s.forecast_mw, actual_mw=s.actual_mw,
                                           band_low_mw=s.band_low_mw, band_high_mw=s.band_high_mw)
                               for s in d.slots]
                cfg = cfg_for(cutoff)
                hit = SeriesResponse(cutoff_local=cutoff, band_nominal_coverage=(cfg.band_hi - cfg.band_lo) / 100,
                                     days=days, points=points)
                self._series.put(cutoff, hit)
            return hit
