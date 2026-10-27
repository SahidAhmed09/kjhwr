import { useMemo, useState } from 'react';
import type { DecisionResponse, MetaResponse } from '../api/types';
import type { ApiResult } from '../api/useApi';
import { TimeChart, type TimePoint } from '../charts/TimeChart';
import { AboutData } from '../components/AboutData';
import { ChartFrame } from '../components/ChartFrame';
import { DataTable, type Column } from '../components/DataTable';
import { ErrorNote, Loading } from '../components/Status';
import {
  dayLabel, fmtDuration, fmtGW, fmtInt, fmtMW, fmtMWh, fmtSignedMW, londonDayOfInstant, londonTime, longDayLabel,
} from '../lib/format';
import { outcomeOf, summariseDecision, type DecisionSummary } from '../lib/summary';

type Slot = DecisionResponse['slots'][number];

const SLOT_MS = 30 * 60 * 1000;
const THREE_HOURS = 3 * 60 * 60 * 1000;

interface Props {
  decision: ApiResult<DecisionResponse>;
  meta: MetaResponse;
  onSeeTrackRecord: () => void;
}

function publishedText(d: DecisionResponse): string {
  const pubs = d.vintages.map((v) => v.publish_utc).sort();
  const first = pubs[0];
  const last = pubs.at(-1);
  if (first === undefined || last === undefined) return 'No forecast had been published by the decision time.';
  const when = (iso: string) => `${londonTime(iso)} on ${londonDayOfInstant(iso)}`;
  return first === last
    ? `The latest forecast you could have used was published at ${when(last)}, before your ${d.cutoff.local} decision time. Anything published after that is ignored.`
    : `The latest forecasts you could have used were published from ${when(first)} to ${when(last)}, before your ${d.cutoff.local} decision time. Anything published after that is ignored.`;
}

function Headline({ d, s }: { d: DecisionResponse; s: DecisionSummary | null }) {
  const day = longDayLabel(d.delivery_date);
  return (
    <h2 className="headline">
      {s === null
        ? `No forecast was available at the ${d.cutoff.local} decision time for ${day}.`
        : `How much wind should you count on for ${day}?`}
    </h2>
  );
}

function Answer({ s }: { s: DecisionSummary | null }) {
  if (s === null) return null;
  return (
    <p className="lead">
      <strong>The forecast says about {fmtGW(s.expectedMeanMW)}.</strong>{' '}
      {s.cautious
        ? <>Forecasts miss, so a cautious plan counts on {fmtGW(s.cautious.meanMW)}.</>
        : <>There is not enough finished-day history yet to say how low it could go.</>}
    </p>
  );
}

function bandNote(b: DecisionResponse['band']): string {
  if (b.method === 'trailing_empirical') {
    return `The grey band on the chart is built from how far the forecast was off over the ${b.n_days} most recent finished days.`;
  }
  if (b.method === 'reduced_history') {
    return `Only ${b.n_days} finished ${b.n_days === 1 ? 'day' : 'days'} of history is available, so treat the grey band on the chart as rough.`;
  }
  return 'No finished days of history are available yet, so there is no grey band for this day.';
}

function PlanTable({ s }: { s: DecisionSummary }) {
  const c = s.cautious;
  return (
    <table className="report">
      <caption className="sr-only">Planning options for the delivery day</caption>
      <tbody>
        <tr>
          <th scope="row">Expected wind</th>
          <td className="num">{fmtGW(s.expectedMeanMW)}</td>
          <td className="muted">Plan on the forecast as published. The day averages this, {fmtMWh(s.expectedEnergyMWh)} in total.</td>
        </tr>
        <tr>
          <th scope="row">Cautious case</th>
          <td className="num">{c ? fmtGW(c.meanMW) : 'Not available'}</td>
          <td className="muted">
            {c
              ? 'The low end of the likely range. Over the past finished days used to build it, the actual fell below this line about 1 half-hour in 10.'
              : 'Needs earlier finished days to measure past errors. Nothing is guessed in its place.'}
          </td>
        </tr>
        <tr>
          <th scope="row">Extra to cover</th>
          <td className="num">{c ? fmtMWh(c.extraMWh) : 'Not available'}</td>
          <td className="muted">
            {c
              ? `What you would need to buy on top of the expected case if wind lands at the cautious case: ${Math.abs(c.extraPeakMW - c.extraMeanMW) < 1 ? `about ${fmtMW(c.extraMeanMW)} more in every half-hour.` : `${fmtInt(c.extraMeanMW)} MW more on average, up to ${fmtMW(c.extraPeakMW)} in the worst half-hour.`}`
              : 'Shown once there is a cautious case.'}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function WhatHappened({ d }: { d: DecisionResponse }) {
  const o = outcomeOf(d);
  if (o === null) {
    return <p className="happened muted">Actual generation for this day is not in the data, so there is nothing to compare.</p>;
  }
  const side = o.errorMW > 0 ? 'too high, the costly side' : o.errorMW < 0 ? 'too low' : 'exactly right';
  return (
    <p className="happened">
      <strong>What actually happened.</strong> Wind averaged {fmtGW(o.actualMeanMW)}, which is{' '}
      {fmtGW(Math.abs(o.errorMW))} {o.errorMW > 0 ? 'below' : o.errorMW < 0 ? 'above' : 'level with'} the forecast, so the
      forecast was {side}.
      {o.rangeN > 0 ? ` Actual wind stayed inside the likely range in ${o.inside} of ${o.rangeN} half-hours.` : ''}
    </p>
  );
}

export function DecisionView({ decision, meta, onSeeTrackRecord }: Props) {
  const [showActual, setShowActual] = useState(false);
  const d = decision.data;

  const summary = useMemo(() => (d ? summariseDecision(d) : null), [d]);
  const points: TimePoint[] = useMemo(
    () => (d ? d.slots.map((s) => ({
      t: Date.parse(s.start_utc), forecast: s.forecast_mw, low: s.band_low_mw, high: s.band_high_mw, actual: s.actual_mw,
    })) : []),
    [d],
  );

  if (!d) {
    return decision.error
      ? <ErrorNote error={decision.error} what="the forecast" onRetry={decision.retry} />
      : <Loading what="the forecast" />;
  }

  const t0 = points[0]?.t ?? 0;
  const ticks = Array.from({ length: 9 }, (_, k) => t0 + k * THREE_HOURS);
  const hasBand = d.band.method !== 'insufficient_history';
  const columns: Column<Slot>[] = [
    { header: 'Half-hour (London)', cell: (r) => londonTime(r.start_utc) },
    { header: 'Forecast (MW)', numeric: true, cell: (r) => (r.forecast_mw === null ? 'no data' : fmtInt(r.forecast_mw)) },
    { header: 'Low end (MW)', numeric: true, cell: (r) => (r.band_low_mw === null ? 'no range' : fmtInt(r.band_low_mw)) },
    { header: 'High end (MW)', numeric: true, cell: (r) => (r.band_high_mw === null ? 'no range' : fmtInt(r.band_high_mw)) },
  ];
  if (showActual) {
    columns.push(
      { header: 'Actual (MW)', numeric: true, cell: (r) => (r.actual_mw === null ? 'no data' : fmtInt(r.actual_mw)) },
      {
        header: 'Forecast minus actual (MW)', numeric: true,
        cell: (r) => (r.forecast_mw === null || r.actual_mw === null ? 'no data' : fmtSignedMW(r.forecast_mw - r.actual_mw).replace(/\s?MW$/, '')),
      },
    );
  }
  columns.push({
    header: 'Forecast published',
    cell: (r) => (r.vintage_publish_utc === null ? 'none' : `${londonTime(r.vintage_publish_utc)} ${londonDayOfInstant(r.vintage_publish_utc)}`),
  });

  return (
    <div className={decision.stale ? 'view is-stale' : 'view'} aria-busy={decision.stale}>
      {decision.error && <ErrorNote error={decision.error} what="this day" onRetry={decision.retry} />}
      <section className="ask">
        <Headline d={d} s={summary} />
        <Answer s={summary} />
      </section>

      <ChartFrame
        title={`Wind through ${dayLabel(d.delivery_date)}`}
        description={hasBand
          ? 'The line is the forecast for each half-hour. The grey band is where the actual wind has usually landed. Hover or use the arrow keys to read a half-hour.'
          : 'The line is the forecast for each half-hour. Hover or use the arrow keys to read a half-hour.'}
        legend={[
          { kind: 'forecast', label: 'Forecast at the decision time' },
          ...(hasBand ? [{ kind: 'range' as const, label: 'Likely range' }] : []),
          ...(showActual ? [{ kind: 'actual' as const, label: 'What actually happened' }] : []),
        ]}
        controls={(
          <label className="check">
            <input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} />
            Show what actually happened
          </label>
        )}
        chart={(
          <TimeChart
            points={points}
            slotMs={SLOT_MS}
            step
            showActual={showActual}
            showBand={hasBand}
            xTicks={ticks}
            xLabel={londonTime}
            tipTitle={(p) => `${londonTime(p.t)} to ${londonTime(p.t + SLOT_MS)}`}
            ariaLabel={`Half-hourly wind forecast for ${longDayLabel(d.delivery_date)}`}
            height={340}
          />
        )}
        table={(
          <DataTable
            caption={`Half-hourly wind forecast for ${longDayLabel(d.delivery_date)}`}
            rows={d.slots}
            rowKey={(r) => r.start_utc}
            columns={columns}
          />
        )}
      />
      {showActual && <WhatHappened d={d} />}

      {summary && (
        <>
          <section className="plain-section" aria-labelledby="used-h">
            <h2 id="used-h" className="step-h">1. Which forecast are you looking at?</h2>
            <p className="basis">{publishedText(d)}</p>
            <p>
              It averages {fmtGW(summary.expectedMeanMW)} over the day and moves between {fmtMW(summary.lowestSlotMW)} and{' '}
              {fmtMW(summary.highestSlotMW)} from one half-hour to the next.
              {summary.freshnessMin === null ? '' : ` It was ${fmtDuration(summary.freshnessMin)} old at the decision time.`}
            </p>
          </section>

          <section className="plain-section" aria-labelledby="range-h">
            <h2 id="range-h" className="step-h">2. How far could it be off?</h2>
            <p>{bandNote(d.band)}</p>
            <p className="muted">
              The band is a guide, not a guarantee.{' '}
              <button type="button" className="link" onClick={onSeeTrackRecord}>See how the forecast has performed</button>.
            </p>
          </section>

          <section className="plain-section" aria-labelledby="plan-h">
            <h2 id="plan-h" className="step-h">3. What could you plan for?</h2>
            <PlanTable s={summary} />
          </section>
        </>
      )}
      <AboutData meta={meta} />
    </div>
  );
}
