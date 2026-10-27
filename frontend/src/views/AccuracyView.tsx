import { useMemo } from 'react';
import type { AccuracyResponse, BucketRow, MetaResponse, Metrics, SeriesResponse } from '../api/types';
import type { ApiResult } from '../api/useApi';
import { BarChart, type BarItem, type Tone } from '../charts/BarChart';
import { TimeChart, type TimePoint } from '../charts/TimeChart';
import { AboutData } from '../components/AboutData';
import { ChartFrame } from '../components/ChartFrame';
import { DataTable } from '../components/DataTable';
import { ErrorNote, Loading } from '../components/Status';
import {
  dayLabel, fmtInt, fmtMW, fmtPct, fmtSigned, fmtSignedMW, londonShortDay, nextDay,
} from '../lib/format';
import { bandCoverage, histogram } from '../lib/summary';

const SLOT_MS = 30 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;
const MINUS = '−';

interface Props {
  accuracy: ApiResult<AccuracyResponse>;
  series: ApiResult<SeriesResponse>;
  meta: MetaResponse;
  /** Selected decision date; its delivery day is outlined in the by-day chart. */
  day: string;
}

const toneOf = (v: number | null): Tone => (v === null || v === 0 ? 'neutral' : v > 0 ? 'over' : 'under');
const sideWords = (v: number): string => (v > 0 ? 'Forecast too high on average' : 'Forecast too low on average');
const num = (n: number): string => (n < 0 ? `${MINUS}${fmtInt(-n)}` : fmtInt(n));

function Headline({ m, cutoff }: { m: Metrics; cutoff: string }) {
  if (m.mae === null) return <h2 className="headline">There are no scored half-hours to measure.</h2>;
  return (
    <h2 className="headline">
      Across January, the forecast available at {cutoff} was off by about {fmtMW(m.mae)} on average, and too high in{' '}
      {fmtPct(m.share_over)} of half-hours.
    </h2>
  );
}

interface MetricRow {
  label: string;
  value: string;
  note: string;
}

function metricRows(a: AccuracyResponse): { main: MetricRow[]; more: MetricRow[] } {
  const m = a.overall;
  const p = a.persistence;
  const main: MetricRow[] = [
    { label: 'Typical miss', value: fmtMW(m.mae), note: 'On average the forecast was this far from what happened, in either direction (mean absolute error).' },
    {
      label: 'Average error', value: fmtSignedMW(m.bias),
      note: 'Forecast minus actual. Positive means the forecast ran too high on average, the costly side.',
    },
    {
      label: '90% shortfall', value: fmtMW(m.shortfall_90),
      note: 'On 9 half-hours in 10 the forecast was no more than this far too high.',
    },
  ];
  if (p.n_paired > 0 && p.baseline.mae !== null && p.forecast.mae !== null) {
    main.push({
      label: 'Against a simple baseline',
      value: `${fmtMW(p.forecast.mae)} vs ${fmtMW(p.baseline.mae)}`,
      note: `Typical miss of the forecast against simply reusing the actual from 2 days earlier, on the same ${fmtInt(p.n_paired)} half-hours.`,
    });
  }
  const more: MetricRow[] = [
    { label: 'Miss as share of output', value: fmtPct(m.wape, 1), note: 'Total absolute miss divided by total actual wind (WAPE).' },
    {
      label: 'Too high, too low', value: `${fmtPct(m.share_over)} / ${fmtPct(m.share_under)}`,
      note: 'Share of half-hours the forecast was above, and below, what happened.',
    },
    { label: 'Big-miss measure', value: fmtMW(m.rmse), note: 'Like the typical miss but counts large misses more heavily (root mean square error).' },
  ];
  return { main, more };
}

function MetricsTable({ rows, caption }: { rows: MetricRow[]; caption: string }) {
  return (
    <table className="report">
      <caption className="sr-only">{caption}</caption>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            <td className="num">{r.value}</td>
            <td className="muted">{r.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function dayItems(a: AccuracyResponse, selectedDelivery: string): BarItem[] {
  return a.by_day.map((r) => {
    const prev = new Date(`${r.key}T12:00:00Z`);
    prev.setUTCDate(prev.getUTCDate() - 1);
    return {
      label: String(new Date(`${r.key}T12:00:00Z`).getUTCDate()),
      tipTitle: `${dayLabel(r.key)} (bought ${dayLabel(prev.toISOString().slice(0, 10))})`,
      bar: r.bias,
      tone: toneOf(r.bias),
      dot: r.mae,
      dotTone: 'neutral',
      highlight: r.key === selectedDelivery,
      rows: r.bias === null
        ? [{ label: 'Error', value: 'no data' }]
        : [
          { label: sideWords(r.bias), value: fmtSignedMW(r.bias), key: r.bias > 0 ? 'over' : 'under' },
          { label: 'Typical miss', value: fmtMW(r.mae), key: 'dot-neutral' },
        ],
      note: `${r.n} of ${r.n_slots} half-hours scored`,
    };
  });
}

function bucketLabel(r: BucketRow): string {
  const f = (v: number) => (v < 0 ? `${MINUS}${-v}` : String(v));
  return `${f(r.lo)} to ${f(r.hi)}`;
}

function missItems(rows: { label: string; title: string; m: Metrics }[]): BarItem[] {
  return rows.map((r) => ({
    label: r.label,
    tipTitle: r.title,
    bar: r.m.mae,
    tone: 'neutral' as const,
    dot: r.m.bias,
    dotTone: toneOf(r.m.bias),
    rows: [
      { label: 'Typical miss', value: fmtMW(r.m.mae), key: 'neutral' as const },
      ...(r.m.bias === null ? [] : [{
        label: sideWords(r.m.bias), value: fmtSignedMW(r.m.bias), key: (r.m.bias > 0 ? 'dot-over' : 'dot-under') as 'dot-over' | 'dot-under',
      }]),
    ],
    note: `${fmtInt(r.m.n)} half-hours`,
  }));
}

const MISS_LEGEND = [
  { kind: 'neutral' as const, label: 'Typical miss' },
  { kind: 'dot-over' as const, label: 'Average error: forecast too high' },
  { kind: 'dot-under' as const, label: 'Average error: forecast too low' },
];

export function AccuracyView({ accuracy, series, meta, day }: Props) {
  const a = accuracy.data;
  const s = series.data;

  const periodPoints: TimePoint[] = useMemo(
    () => (s ? s.points.map((p) => ({ t: Date.parse(p.start_utc), forecast: p.forecast_mw, low: null, high: null, actual: p.actual_mw })) : []),
    [s],
  );
  const errors = useMemo(
    () => (s ? s.points.flatMap((p) => (p.forecast_mw !== null && p.actual_mw !== null ? [p.forecast_mw - p.actual_mw] : [])) : []),
    [s],
  );
  const bins = useMemo(() => histogram(errors, 1000), [errors]);
  const coverage = useMemo(() => (s ? bandCoverage(s.points) : null), [s]);
  const dailyAverages = useMemo(() => {
    if (!s) return [];
    return s.days.map((d) => {
      const pts = s.points.filter((p) => p.decision_date === d.decision_date && p.forecast_mw !== null && p.actual_mw !== null);
      const f = pts.reduce((x, p) => x + (p.forecast_mw as number), 0) / (pts.length || 1);
      const ac = pts.reduce((x, p) => x + (p.actual_mw as number), 0) / (pts.length || 1);
      return { day: d.delivery_date, n: pts.length, forecast: pts.length ? f : null, actual: pts.length ? ac : null };
    });
  }, [s]);

  if (!a) {
    return accuracy.error
      ? <ErrorNote error={accuracy.error} what="the accuracy figures" onRetry={accuracy.retry} />
      : <Loading what="the accuracy figures" />;
  }

  const rows = metricRows(a);
  const decisionLead = a.by_lead.length
    ? `At your ${a.cutoff_local} decision time the forecast used is ${Math.min(...a.by_lead.map((r) => r.lo))} to ${Math.max(...a.by_lead.map((r) => r.hi))} hours ahead. `
    : '';
  const periodFirst = periodPoints[0]?.t ?? 0;
  const periodTicks = Array.from({ length: Math.ceil((s?.days.length ?? 0) / 5) + 1 }, (_, k) => periodFirst + k * 5 * DAY_MS);

  return (
    <div className={accuracy.stale || series.stale ? 'view is-stale' : 'view'} aria-busy={accuracy.stale || series.stale}>
      {accuracy.error && <ErrorNote error={accuracy.error} what="the accuracy figures" onRetry={accuracy.retry} />}
      <section className="ask">
        <Headline m={a.overall} cutoff={a.cutoff_local} />
        <p className="muted basis">
          Measured over {fmtInt(a.counts.n_scored)} of {fmtInt(a.counts.n_slots)} half-hours in the window.{' '}
          {a.counts.n_missing_forecast + a.counts.n_missing_actual === 0
            ? 'None were missing a forecast or an actual.'
            : `${fmtInt(a.counts.n_missing_forecast)} had no forecast and ${fmtInt(a.counts.n_missing_actual)} had no actual; they are left out, not filled.`}
        </p>
      </section>

      <section className="plain-section" aria-labelledby="size-h">
        <h2 id="size-h" className="step-h">1. How big are the misses?</h2>
        <MetricsTable rows={rows.main} caption="Key accuracy measures" />
        <details className="disclosure">
          <summary>More measures</summary>
          <MetricsTable rows={rows.more} caption="More accuracy measures" />
        </details>
      </section>

      <section className="plain-section" aria-labelledby="days-h">
        <h2 id="days-h" className="step-h">2. How did it go, day by day?</h2>
        {series.error && <ErrorNote error={series.error} what="the period charts" onRetry={series.retry} />}
        {s ? (
          <ChartFrame
            title="Forecast and actual across the whole period"
            description="Each half-hour of every delivery day, using the forecast known at the decision time the day before."
            legend={[{ kind: 'forecast', label: 'Forecast at the decision time' }, { kind: 'actual', label: 'What actually happened' }]}
            chart={(
              <TimeChart
                points={periodPoints}
                slotMs={SLOT_MS}
                step={false}
                showActual
                showBand={false}
                xTicks={periodTicks}
                xLabel={londonShortDay}
                tipTitle={(p) => `${londonShortDay(p.t)}, ${new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit', hour12: false }).format(p.t)}`}
                ariaLabel="Forecast and actual wind generation across the whole period"
                height={320}
              />
            )}
            table={(
              <DataTable
                caption="Daily averages of forecast and actual wind generation"
                rows={dailyAverages}
                rowKey={(r) => r.day}
                columns={[
                  { header: 'Delivery day', cell: (r) => dayLabel(r.day) },
                  { header: 'Half-hours', numeric: true, cell: (r) => fmtInt(r.n) },
                  { header: 'Average forecast (MW)', numeric: true, cell: (r) => (r.forecast === null ? 'no data' : fmtInt(r.forecast)) },
                  { header: 'Average actual (MW)', numeric: true, cell: (r) => (r.actual === null ? 'no data' : fmtInt(r.actual)) },
                  {
                    header: 'Average error (MW)', numeric: true,
                    cell: (r) => (r.forecast === null || r.actual === null ? 'no data' : fmtSigned(r.forecast - r.actual)),
                  },
                ]}
              />
            )}
          />
        ) : !series.error && <Loading what="the period charts" />}

        <ChartFrame
          title="Error by day"
          description="Average error for each delivery day. Bars above the line are over-forecast days; the dot is the typical miss. The day you picked is outlined."
          legend={[
            { kind: 'over', label: 'Forecast too high' },
            { kind: 'under', label: 'Forecast too low' },
            { kind: 'dot-neutral', label: 'Typical miss' },
          ]}
          chart={<BarChart items={dayItems(a, nextDay(day))} unit="MW" ariaLabel="Average forecast error for each delivery day" height={300} labelWidth={26} />}
          table={(
            <DataTable
              caption="Forecast error by delivery day"
              rows={a.by_day}
              rowKey={(r) => r.key}
              columns={[
                { header: 'Delivery day', cell: (r) => dayLabel(r.key) },
                { header: 'Half-hours scored', numeric: true, cell: (r) => `${r.n} of ${r.n_slots}` },
                { header: 'Average error (MW)', numeric: true, cell: (r) => fmtSigned(r.bias) },
                { header: 'Typical miss (MW)', numeric: true, cell: (r) => (r.mae === null ? 'no data' : fmtInt(r.mae)) },
                { header: 'Too high', numeric: true, cell: (r) => fmtPct(r.share_over) },
              ]}
            />
          )}
        />
      </section>

      {s && coverage && (
        <section className="plain-section" aria-labelledby="cal-h">
          <h2 id="cal-h" className="step-h">3. Does the likely range hold?</h2>
          {coverage.n === 0 ? (
            <p>No half-hours had a likely range yet, so there is nothing to check it against.</p>
          ) : (
            <>
              <p>
                The range on the decision view is built to contain the actual about{' '}
                {fmtPct(s.band_nominal_coverage)} of the time. Over the {fmtInt(coverage.n)} half-hours that had one,
                the actual landed inside it {fmtPct(coverage.inside / coverage.n, 1)} of the time
                {coverage.inside / coverage.n >= s.band_nominal_coverage - 0.03
                  ? ', close to or better than the aim'
                  : ', below the aim, so the range has been somewhat narrower than it should be'}.
                It fell below the range {fmtPct(coverage.below / coverage.n, 1)} of the time (wind lower than the
                cautious case) and above it {fmtPct(coverage.above / coverage.n, 1)}.
              </p>
              <p className="muted">
                {s.days.filter((d) => d.band_method !== 'trailing_empirical').length} of {s.days.length} days had a shorter
                history than the target, or none, and are included as published. Each range uses only days finished
                before its own decision time.
              </p>
            </>
          )}
        </section>
      )}

      <details className="disclosure more-detail">
        <summary>More detail for analysts</summary>
        <div className="chart-grid">
          <ChartFrame
            title="Error by lead time"
            description={`${decisionLead}How the miss changes with how far ahead each forecast was made, using every forecast published. Negative values are forecasts made after the half-hour had begun.`}
            legend={MISS_LEGEND}
            chart={(
              <BarChart
                items={missItems(a.lead_all_vintages.map((r) => ({ label: bucketLabel(r), title: `${bucketLabel(r)} hours ahead`, m: r })))}
                unit="MW"
                ariaLabel="Forecast error by how many hours ahead the forecast was made"
                height={300}
                labelWidth={68}
              />
            )}
            table={(
              <DataTable
                caption="Forecast error by lead time, every forecast published"
                rows={a.lead_all_vintages}
                rowKey={(r) => String(r.key)}
                columns={[
                  { header: 'Hours ahead', cell: (r) => bucketLabel(r) },
                  { header: 'Forecasts', numeric: true, cell: (r) => fmtInt(r.n) },
                  { header: 'Average error (MW)', numeric: true, cell: (r) => fmtSigned(r.bias) },
                  { header: 'Typical miss (MW)', numeric: true, cell: (r) => (r.mae === null ? 'no data' : fmtInt(r.mae)) },
                  { header: 'Too high', numeric: true, cell: (r) => fmtPct(r.share_over) },
                ]}
              />
            )}
          />

          <ChartFrame
            title="Error by time of day"
            description="The same measures for each hour of the London day, across all delivery days."
            legend={MISS_LEGEND}
            chart={(
              <BarChart
                items={missItems(a.by_hour.map((r) => ({ label: String(r.key).padStart(2, '0'), title: `${String(r.key).padStart(2, '0')}:00 to ${String(r.key).padStart(2, '0')}:59`, m: r })))}
                unit="MW"
                ariaLabel="Forecast error by hour of the day"
                height={300}
                labelWidth={26}
              />
            )}
            table={(
              <DataTable
                caption="Forecast error by hour of day"
                rows={a.by_hour}
                rowKey={(r) => String(r.key)}
                columns={[
                  { header: 'Hour (London)', cell: (r) => `${String(r.key).padStart(2, '0')}:00` },
                  { header: 'Half-hours', numeric: true, cell: (r) => fmtInt(r.n) },
                  { header: 'Average error (MW)', numeric: true, cell: (r) => fmtSigned(r.bias) },
                  { header: 'Typical miss (MW)', numeric: true, cell: (r) => (r.mae === null ? 'no data' : fmtInt(r.mae)) },
                  { header: 'Too high', numeric: true, cell: (r) => fmtPct(r.share_over) },
                ]}
              />
            )}
          />

          {s ? (
            <ChartFrame
              title="How big the errors are"
              description="Count of half-hours by size of error, in 1,000 MW steps. Each label is the lower edge of its step. Red bars are over-forecast."
              legend={[{ kind: 'over', label: 'Forecast too high' }, { kind: 'under', label: 'Forecast too low' }]}
              chart={(
                <BarChart
                  items={bins.map((b) => ({
                    label: '',
                    tipTitle: `${num(b.lo)} to ${num(b.hi)} MW`,
                    bar: b.count,
                    tone: b.lo >= 0 ? 'over' : 'under',
                    rows: [{ label: b.lo >= 0 ? 'Half-hours, forecast too high' : 'Half-hours, forecast too low', value: fmtInt(b.count), key: b.lo >= 0 ? 'over' : 'under' }],
                    note: `${fmtPct(b.count / errors.length, 1)} of ${fmtInt(errors.length)} scored half-hours`,
                  }))}
                  unit="half-hours"
                  ariaLabel="Distribution of forecast errors"
                  height={300}
                  labelWidth={44}
                  edgeLabels={[...bins.map((b) => b.lo), bins.at(-1)?.hi ?? 0].map((v) => (v === 0 ? '0' : `${num(v / 1000)}K`))}
                />
              )}
              table={(
                <DataTable
                  caption="Distribution of forecast errors"
                  rows={bins}
                  rowKey={(b) => String(b.lo)}
                  columns={[
                    { header: 'Error from (MW)', numeric: true, cell: (b) => num(b.lo) },
                    { header: 'to (MW)', numeric: true, cell: (b) => num(b.hi) },
                    { header: 'Half-hours', numeric: true, cell: (b) => fmtInt(b.count) },
                    { header: 'Share', numeric: true, cell: (b) => fmtPct(b.count / errors.length, 1) },
                  ]}
                />
              )}
            />
          ) : null}
        </div>
        <section className="plain-section" aria-labelledby="level-h">
          <h3 id="level-h">Error by forecast level</h3>
          <p className="muted">Whether the forecast misses more when it predicts a lot of wind or a little.</p>
          <DataTable
            caption="Forecast error by forecast level"
            rows={a.by_level}
            rowKey={(r) => String(r.key)}
            columns={[
              { header: 'Forecast level (MW)', cell: (r) => `${fmtInt(r.lo)} to ${fmtInt(r.hi)}` },
              { header: 'Half-hours', numeric: true, cell: (r) => fmtInt(r.n) },
              { header: 'Average error (MW)', numeric: true, cell: (r) => fmtSigned(r.bias) },
              { header: 'Typical miss (MW)', numeric: true, cell: (r) => (r.mae === null ? 'no data' : fmtInt(r.mae)) },
              { header: 'Too high', numeric: true, cell: (r) => fmtPct(r.share_over) },
            ]}
          />
        </section>
      </details>

      <AboutData meta={meta} />
    </div>
  );
}
