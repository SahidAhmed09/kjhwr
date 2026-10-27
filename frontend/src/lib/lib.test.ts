// Unit tests use tiny hand-made inputs. They are test fixtures only and never reach the UI.
import { describe, expect, it } from 'vitest';
import type { DecisionResponse, SlotOut } from '../api/types';
import { dateRange, dayLabel, fmtDuration, fmtGW, fmtInt, fmtSignedMW, londonTime, nextDay } from './format';
import { bandCoverage, histogram, outcomeOf, summariseDecision } from './summary';

const slot = (f: number | null, lo: number | null, hi: number | null): SlotOut => ({
  start_utc: '2026-01-15T00:00:00Z', start_local: '', forecast_mw: f, actual_mw: null,
  vintage_publish_utc: '2026-01-14T07:30:00Z', lead_h: 16.5, band_low_mw: lo, band_high_mw: hi,
});

const decision = (slots: SlotOut[]): DecisionResponse => ({
  decision_date: '2026-01-14', delivery_date: '2026-01-15',
  cutoff: { local: '09:20', utc: '2026-01-14T09:20:00Z', timezone: 'Europe/London' },
  n_slots: slots.length, n_missing_forecast: 0, n_missing_actual: 0, n_scored: 0,
  band: { method: 'trailing_empirical', label: '', n_days: 7, n_errors: 1, p10: 0, p90: 0 },
  vintages: [{ publish_utc: '2026-01-14T07:30:00Z', n_slots: slots.length }],
  slots,
});

describe('format', () => {
  it('formats numbers with a true minus sign and grouping', () => {
    expect(fmtInt(15834)).toBe('15,834');
    expect(fmtInt(-1748)).toBe('−1,748');
    expect(fmtSignedMW(1748.4)).toBe('+1,748\u00a0MW');
    expect(fmtGW(15834)).toBe('15.8\u00a0GW');
  });
  it('formats London times and dates', () => {
    expect(londonTime('2026-01-14T09:20:00Z')).toBe('09:20');
    expect(londonTime('2026-07-01T08:20:00Z')).toBe('09:20');
    expect(dayLabel('2026-01-15')).toBe('Thu 15 Jan');
  });
  it('formats durations', () => {
    expect(fmtDuration(110)).toBe('1 h 50 min');
    expect(fmtDuration(40)).toBe('40 min');
    expect(fmtDuration(120)).toBe('2 h');
  });
});

describe('summariseDecision', () => {
  it('computes energy, cautious case and extra volume by hand', () => {
    // 4 slots of 0.5 h: forecast 100 each = 200 MWh; low 60 each = 120 MWh; extra 80 MWh = 40 MW mean
    const s = summariseDecision(decision([100, 100, 100, 100].map((f) => slot(f, 60, 130))));
    expect(s?.expectedEnergyMWh).toBeCloseTo(200);
    expect(s?.expectedMeanMW).toBeCloseTo(100);
    expect(s?.cautious?.energyMWh).toBeCloseTo(120);
    expect(s?.cautious?.extraMWh).toBeCloseTo(80);
    expect(s?.cautious?.extraMeanMW).toBeCloseTo(40);
    expect(s?.cautious?.extraPeakMW).toBeCloseTo(40);
    expect(s?.freshnessMin).toBeCloseTo(110);
  });
  it('floors the cautious wind at zero', () => {
    const s = summariseDecision(decision([slot(100, -50, 150)]));
    expect(s?.cautious?.energyMWh).toBe(0);
    expect(s?.cautious?.extraMWh).toBeCloseTo(50);
  });
  it('has no cautious case when any band value is missing', () => {
    expect(summariseDecision(decision([slot(100, null, null), slot(100, 60, 130)]))?.cautious).toBeNull();
  });
  it('ignores slots without a forecast and returns null when none has one', () => {
    expect(summariseDecision(decision([slot(null, null, null)]))).toBeNull();
    expect(summariseDecision(decision([slot(100, 60, 130), slot(null, null, null)]))?.nForecast).toBe(1);
  });
});

describe('dates', () => {
  it('walks calendar days across a month end', () => {
    expect(nextDay('2026-01-31')).toBe('2026-02-01');
    expect(dateRange('2026-01-30', '2026-02-02')).toEqual(['2026-01-30', '2026-01-31', '2026-02-01', '2026-02-02']);
  });
  it('accepts epoch milliseconds for London time', () => {
    expect(londonTime(Date.parse('2026-07-01T08:20:00Z'))).toBe('09:20');
  });
});

describe('outcomeOf', () => {
  it('compares forecast with actual by hand and counts slots inside the range', () => {
    const withActual = (f: number, a: number, lo: number, hi: number): SlotOut => ({ ...slot(f, lo, hi), actual_mw: a });
    // forecast 100,100 vs actual 90,130 -> actual mean 110, error -10; range [80,120]: inside 1 of 2
    const o = outcomeOf(decision([withActual(100, 90, 80, 120), withActual(100, 130, 80, 120)]));
    expect(o).toEqual({ n: 2, actualMeanMW: 110, forecastMeanMW: 100, errorMW: -10, inside: 1, rangeN: 2 });
  });
  it('is null when there are no actuals', () => {
    expect(outcomeOf(decision([slot(100, 80, 120)]))).toBeNull();
  });
});

describe('bandCoverage and histogram', () => {
  it('counts inside, below and above, skipping incomplete points', () => {
    const c = bandCoverage([
      { actual_mw: 5, band_low_mw: 0, band_high_mw: 10 },
      { actual_mw: -1, band_low_mw: 0, band_high_mw: 10 },
      { actual_mw: 11, band_low_mw: 0, band_high_mw: 10 },
      { actual_mw: 10, band_low_mw: 0, band_high_mw: 10 },
      { actual_mw: null, band_low_mw: 0, band_high_mw: 10 },
      { actual_mw: 5, band_low_mw: null, band_high_mw: null },
    ]);
    expect(c).toEqual({ n: 4, inside: 2, below: 1, above: 1 });
  });
  it('bins values aligned to the width and keeps every value', () => {
    const h = histogram([-1500, -10, 0, 999, 1000, 2500], 1000);
    expect(h.map((b) => [b.lo, b.count])).toEqual([[-2000, 1], [-1000, 1], [0, 2], [1000, 1], [2000, 1]]);
    expect(h.reduce((a, b) => a + b.count, 0)).toBe(6);
  });
  it('returns no bins for no values', () => {
    expect(histogram([], 1000)).toEqual([]);
  });
});
