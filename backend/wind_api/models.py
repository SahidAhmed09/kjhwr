"""Typed response models (these drive the OpenAPI schema)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

OptFloat = float | None


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable explanation of what went wrong.")


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' while the process is serving.")
    data_file_present: bool = Field(description="Whether the snapshot file exists on disk.")
    data_loaded: bool = Field(description="Whether the snapshot has been loaded into memory yet (loading is lazy).")


# ---- /api/meta
class ServiceInfo(BaseModel):
    name: str
    version: str


class DataInfo(BaseModel):
    fetched_at: str
    base_url: str
    publish_from: str
    publish_to: str
    settlement_from: date
    settlement_to: date
    n_actual_rows: int
    n_forecast_rows: int
    n_publish_times: int
    sha256: str = Field(description="SHA-256 of the snapshot file.")


class DecisionWindow(BaseModel):
    first: date
    last: date


class Defaults(BaseModel):
    cutoff: str
    timezone: str
    error_definition: str


class MetaResponse(BaseModel):
    service: ServiceInfo
    data: DataInfo
    decision_window: DecisionWindow = Field(
        description="Decision dates the API accepts. Delivery day is the following day.")
    defaults: Defaults
    notes: list[str] = Field(description="Known assumptions and unverified points about the data.")


# ---- /api/decision
class CutoffInfo(BaseModel):
    local: str = Field(description="HH:MM Europe/London wall-clock time on the decision date.")
    utc: str
    timezone: str


class BandInfo(BaseModel):
    method: str = Field(description="trailing_empirical | reduced_history | insufficient_history")
    label: str
    n_days: int
    n_errors: int
    p10: OptFloat = Field(description="Low percentile of past (forecast - actual) error, MW.")
    p90: OptFloat = Field(description="High percentile of past (forecast - actual) error, MW.")


class VintageUse(BaseModel):
    publish_utc: str
    n_slots: int


class SlotOut(BaseModel):
    start_utc: str
    start_local: str
    forecast_mw: OptFloat = Field(description="Hourly forecast known at the cut-off; null if none was available.")
    actual_mw: OptFloat = Field(description="Ex-post actual. NOT known at decision time; for replay/evaluation only.")
    vintage_publish_utc: str | None
    lead_h: OptFloat = Field(description="Slot start minus vintage publish time, hours.")
    band_low_mw: OptFloat = Field(description="Low end of the expected range of the actual: forecast - p90 error.")
    band_high_mw: OptFloat = Field(description="High end of the expected range of the actual: forecast - p10 error.")


class DecisionResponse(BaseModel):
    decision_date: date
    delivery_date: date
    cutoff: CutoffInfo
    n_slots: int = Field(description="46, 48 or 50 half-hour slots in the London delivery day.")
    n_missing_forecast: int
    n_missing_actual: int
    n_scored: int
    band: BandInfo
    vintages: list[VintageUse]
    slots: list[SlotOut]


# ---- /api/accuracy
class Metrics(BaseModel):
    n: int
    mae: OptFloat = Field(description="Mean absolute error, MW.")
    rmse: OptFloat
    bias: OptFloat = Field(description="Mean of (forecast - actual), MW. Positive = over-forecast.")
    wape: OptFloat = Field(description="Sum |error| / sum actual (a fraction, not a percentage).")
    abs_pct: dict[str, OptFloat]
    signed_pct: dict[str, OptFloat]
    share_over: OptFloat = Field(description="Share of slots with forecast > actual.")
    share_under: OptFloat
    share_exact: OptFloat
    shortfall_90: OptFloat = Field(description="max(0, P90 of forecast - actual), MW.")


class DayRow(Metrics):
    key: str = Field(description="Delivery date (London).")
    n_slots: int
    n_missing_forecast: int
    n_missing_actual: int


class HourRow(Metrics):
    key: int = Field(description="London wall-clock hour of the slot start (0-23).")


class BucketRow(Metrics):
    key: float = Field(description="Lower edge of the bucket.")
    lo: float
    hi: float


class Counts(BaseModel):
    n_days: int
    n_slots: int
    n_missing_forecast: int
    n_missing_actual: int
    n_missing_both: int
    n_scored: int


class AccuracyConfig(BaseModel):
    cutoff_time: str
    tz: str
    error: str
    lead_bucket_h: float
    level_bin_mw: float


class Persistence(BaseModel):
    baseline_name: str
    n_paired: int
    n_missing_baseline: int
    forecast: Metrics
    baseline: Metrics
    skill_mae: OptFloat = Field(description="1 - MAE(forecast)/MAE(baseline) on paired slots.")
    skill_rmse: OptFloat


class AccuracyResponse(BaseModel):
    cutoff_local: str
    config: AccuracyConfig
    counts: Counts
    overall: Metrics
    by_day: list[DayRow]
    by_hour: list[HourRow]
    by_lead: list[BucketRow] = Field(description="Decision-time vintage, by lead time (hours).")
    by_level: list[BucketRow] = Field(description="By forecast level (MW).")
    lead_all_vintages: list[BucketRow] = Field(description="Every vintage, by lead time (hours); can be negative.")
    persistence: Persistence


# ---- /api/series
class SeriesPoint(BaseModel):
    start_utc: str
    decision_date: date = Field(description="Decision date whose cut-off produced this forecast.")
    forecast_mw: OptFloat = Field(description="Forecast known at that decision's cut-off; null if none.")
    actual_mw: OptFloat = Field(description="Ex-post actual; null if missing.")
    band_low_mw: OptFloat
    band_high_mw: OptFloat


class SeriesDay(BaseModel):
    decision_date: date
    delivery_date: date
    band_method: str = Field(description="trailing_empirical | reduced_history | insufficient_history")


class SeriesResponse(BaseModel):
    cutoff_local: str
    band_nominal_coverage: float = Field(
        description="Share of actuals the band is designed to contain (e.g. 0.8 for P10-P90).")
    days: list[SeriesDay]
    points: list[SeriesPoint] = Field(description="Every half-hour slot of every delivery day, in time order.")
