// Mirrors backend/wind_api/models.py. Keep in sync with /openapi.json.

export interface PercentileMap {
  [key: string]: number | null;
}

export interface Metrics {
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  wape: number | null;
  abs_pct: PercentileMap;
  signed_pct: PercentileMap;
  share_over: number | null;
  share_under: number | null;
  share_exact: number | null;
  shortfall_90: number | null;
}

export interface DayRow extends Metrics {
  key: string;
  n_slots: number;
  n_missing_forecast: number;
  n_missing_actual: number;
}

export interface HourRow extends Metrics {
  key: number;
}

export interface BucketRow extends Metrics {
  key: number;
  lo: number;
  hi: number;
}

export interface Counts {
  n_days: number;
  n_slots: number;
  n_missing_forecast: number;
  n_missing_actual: number;
  n_missing_both: number;
  n_scored: number;
}

export interface Persistence {
  baseline_name: string;
  n_paired: number;
  n_missing_baseline: number;
  forecast: Metrics;
  baseline: Metrics;
  skill_mae: number | null;
  skill_rmse: number | null;
}

export interface AccuracyResponse {
  cutoff_local: string;
  config: {
    cutoff_time: string;
    tz: string;
    error: string;
    lead_bucket_h: number;
    level_bin_mw: number;
  };
  counts: Counts;
  overall: Metrics;
  by_day: DayRow[];
  by_hour: HourRow[];
  by_lead: BucketRow[];
  by_level: BucketRow[];
  lead_all_vintages: BucketRow[];
  persistence: Persistence;
}

export type BandMethod = 'trailing_empirical' | 'reduced_history' | 'insufficient_history';

export interface BandInfo {
  method: BandMethod;
  label: string;
  n_days: number;
  n_errors: number;
  p10: number | null;
  p90: number | null;
}

export interface SlotOut {
  start_utc: string;
  start_local: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  vintage_publish_utc: string | null;
  lead_h: number | null;
  band_low_mw: number | null;
  band_high_mw: number | null;
}

export interface DecisionResponse {
  decision_date: string;
  delivery_date: string;
  cutoff: { local: string; utc: string; timezone: string };
  n_slots: number;
  n_missing_forecast: number;
  n_missing_actual: number;
  n_scored: number;
  band: BandInfo;
  vintages: { publish_utc: string; n_slots: number }[];
  slots: SlotOut[];
}

export interface MetaResponse {
  service: { name: string; version: string };
  data: {
    fetched_at: string;
    base_url: string;
    publish_from: string;
    publish_to: string;
    settlement_from: string;
    settlement_to: string;
    n_actual_rows: number;
    n_forecast_rows: number;
    n_publish_times: number;
    sha256: string;
  };
  decision_window: { first: string; last: string };
  defaults: { cutoff: string; timezone: string; error_definition: string };
  notes: string[];
}

export interface SeriesPoint {
  start_utc: string;
  decision_date: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  band_low_mw: number | null;
  band_high_mw: number | null;
}

export interface SeriesResponse {
  cutoff_local: string;
  band_nominal_coverage: number;
  days: { decision_date: string; delivery_date: string; band_method: BandMethod }[];
  points: SeriesPoint[];
}
