import type { DecisionResponse } from '../api/types';

const SLOT_HOURS = 0.5;

export interface CautiousCase {
  /** Total wind energy if the low end of the range happens (wind cannot be below zero). */
  energyMWh: number;
  meanMW: number;
  /** Extra energy to buy compared with the expected case. */
  extraMWh: number;
  extraMeanMW: number;
  /** Largest extra power needed in any single half-hour. */
  extraPeakMW: number;
}

export interface DecisionSummary {
  /** Slots that have a forecast. */
  nForecast: number;
  expectedEnergyMWh: number;
  expectedMeanMW: number;
  lowestSlotMW: number;
  highestSlotMW: number;
  /** null when the band is unavailable or does not cover every forecast slot. */
  cautious: CautiousCase | null;
  /** Minutes between the newest vintage used and the cut-off; null if no vintage was used. */
  freshnessMin: number | null;
  newestPublishUtc: string | null;
}

export function summariseDecision(d: DecisionResponse): DecisionSummary | null {
  const withForecast = d.slots.filter((s) => s.forecast_mw !== null);
  if (withForecast.length === 0) return null;

  const mw = withForecast.map((s) => s.forecast_mw as number);
  const energy = mw.reduce((a, b) => a + b, 0) * SLOT_HOURS;

  const bandComplete = withForecast.every((s) => s.band_low_mw !== null);
  let cautious: CautiousCase | null = null;
  if (bandComplete) {
    const low = withForecast.map((s) => Math.max(0, s.band_low_mw as number));
    const lowEnergy = low.reduce((a, b) => a + b, 0) * SLOT_HOURS;
    const extra = mw.map((f, i) => f - (low[i] as number));
    cautious = {
      energyMWh: lowEnergy,
      meanMW: lowEnergy / (low.length * SLOT_HOURS),
      extraMWh: energy - lowEnergy,
      extraMeanMW: (energy - lowEnergy) / (low.length * SLOT_HOURS),
      extraPeakMW: Math.max(...extra),
    };
  }

  const newest = d.vintages.map((v) => v.publish_utc).sort().at(-1) ?? null;
  const freshnessMin = newest === null ? null : (Date.parse(d.cutoff.utc) - Date.parse(newest)) / 60000;

  return {
    nForecast: withForecast.length,
    expectedEnergyMWh: energy,
    expectedMeanMW: energy / (withForecast.length * SLOT_HOURS),
    lowestSlotMW: Math.min(...mw),
    highestSlotMW: Math.max(...mw),
    cautious,
    freshnessMin,
    newestPublishUtc: newest,
  };
}

export interface Coverage {
  /** Slots with a band, a forecast and an actual. */
  n: number;
  inside: number;
  below: number;
  above: number;
}

/** How often actuals fell inside / below / above the band that was published for them. */
export function bandCoverage(
  points: { actual_mw: number | null; band_low_mw: number | null; band_high_mw: number | null }[],
): Coverage {
  const c: Coverage = { n: 0, inside: 0, below: 0, above: 0 };
  for (const p of points) {
    if (p.actual_mw === null || p.band_low_mw === null || p.band_high_mw === null) continue;
    c.n += 1;
    if (p.actual_mw < p.band_low_mw) c.below += 1;
    else if (p.actual_mw > p.band_high_mw) c.above += 1;
    else c.inside += 1;
  }
  return c;
}

export interface HistBin {
  lo: number;
  hi: number;
  count: number;
}

/** Fixed-width histogram of signed errors; bins are aligned to multiples of `width`. */
export function histogram(values: number[], width: number): HistBin[] {
  if (values.length === 0) return [];
  const first = Math.floor(Math.min(...values) / width);
  const last = Math.floor(Math.max(...values) / width);
  const bins: HistBin[] = [];
  for (let i = first; i <= last; i += 1) bins.push({ lo: i * width, hi: (i + 1) * width, count: 0 });
  for (const v of values) (bins[Math.floor(v / width) - first] as HistBin).count += 1;
  return bins;
}

export interface Outcome {
  /** Slots with both a forecast and an actual. */
  n: number;
  actualMeanMW: number;
  forecastMeanMW: number;
  /** Mean of forecast minus actual, MW. Positive = forecast too high. */
  errorMW: number;
  /** Slots whose actual fell inside the published range, out of `rangeN` that had one. */
  inside: number;
  rangeN: number;
}

/** What actually happened on the delivery day, from slots that have both a forecast and an actual. */
export function outcomeOf(d: DecisionResponse): Outcome | null {
  const both = d.slots.filter((s) => s.forecast_mw !== null && s.actual_mw !== null);
  if (both.length === 0) return null;
  const f = both.reduce((a, s) => a + (s.forecast_mw as number), 0) / both.length;
  const a = both.reduce((x, s) => x + (s.actual_mw as number), 0) / both.length;
  const ranged = both.filter((s) => s.band_low_mw !== null && s.band_high_mw !== null);
  const inside = ranged.filter((s) => (s.actual_mw as number) >= (s.band_low_mw as number)
    && (s.actual_mw as number) <= (s.band_high_mw as number)).length;
  return { n: both.length, actualMeanMW: a, forecastMeanMW: f, errorMW: f - a, inside, rangeN: ranged.length };
}
