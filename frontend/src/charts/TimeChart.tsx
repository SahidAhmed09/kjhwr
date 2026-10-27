import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { fmtAxis, linear, niceTicks, useWidth } from './chartUtils';
import { Tooltip, useChartTip, type TipRow } from './Tooltip';
import { fmtMW } from '../lib/format';

export interface TimePoint {
  /** Start of the slot, epoch milliseconds. */
  t: number;
  forecast: number | null;
  low: number | null;
  high: number | null;
  actual: number | null;
}

interface Props {
  points: TimePoint[];
  /** Width of one slot in ms. Step charts draw each value flat across its slot. */
  slotMs: number;
  step: boolean;
  showActual: boolean;
  showBand: boolean;
  xTicks: number[];
  xLabel: (t: number) => string;
  tipTitle: (p: TimePoint) => string;
  tipNote?: (p: TimePoint) => string | undefined;
  ariaLabel: string;
  height: number;
}

/** A run of consecutive points whose picked value is not null. */
function runs(points: TimePoint[], pick: (p: TimePoint) => number | null): TimePoint[][] {
  const out: TimePoint[][] = [];
  let cur: TimePoint[] = [];
  for (const p of points) {
    if (pick(p) === null) {
      if (cur.length) out.push(cur);
      cur = [];
    } else cur.push(p);
  }
  if (cur.length) out.push(cur);
  return out;
}

export function TimeChart({
  points, slotMs, step, showActual, showBand, xTicks, xLabel, tipTitle, tipNote, ariaLabel, height,
}: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const width = useWidth(wrap);
  const [active, setActive] = useState<number | null>(null);

  const narrow = width < 520;
  const m = { l: narrow ? 40 : 52, r: narrow || !showActual ? 12 : 72, t: 24, b: 28 };
  const iw = Math.max(0, width - m.l - m.r);
  const ih = height - m.t - m.b;

  const t0 = points[0]?.t ?? 0;
  const t1 = (points.at(-1)?.t ?? 0) + (step ? slotMs : 0);

  const { yTicks, ymax } = useMemo(() => {
    let max = 0;
    for (const p of points) {
      for (const v of [p.forecast, p.high, showActual ? p.actual : null]) if (v !== null && v > max) max = v;
    }
    const n = niceTicks(0, max || 1, 5);
    return { yTicks: n.ticks, ymax: n.hi };
  }, [points, showActual]);

  const x = linear(t0, t1, m.l, m.l + iw);
  const y = linear(0, ymax, m.t + ih, m.t);
  const slotW = step ? x(t0 + slotMs) - x(t0) : 0;

  const linePath = (rs: TimePoint[][], pick: (p: TimePoint) => number | null): string =>
    rs.map((run) => run.map((p, i) => {
      const yy = y(pick(p) as number);
      if (!step) return `${i === 0 ? 'M' : 'L'}${x(p.t).toFixed(1)},${yy.toFixed(1)}`;
      const xs = x(p.t).toFixed(1);
      const xe = x(p.t + slotMs).toFixed(1);
      return `${i === 0 ? 'M' : 'L'}${xs},${yy.toFixed(1)}H${xe}`;
    }).join('')).join('');

  const bandPath = !showBand ? '' : (() => {
    return runs(points, (p) => (p.low !== null && p.high !== null ? 1 : null)).map((run) => {
      const top = run.map((p, i) => (step
        ? `${i === 0 ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.high as number).toFixed(1)}L${x(p.t + slotMs).toFixed(1)},${y(p.high as number).toFixed(1)}`
        : `${i === 0 ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.high as number).toFixed(1)}`)).join('');
      const bottom = [...run].reverse().map((p) => (step
        ? `L${x(p.t + slotMs).toFixed(1)},${y(p.low as number).toFixed(1)}L${x(p.t).toFixed(1)},${y(p.low as number).toFixed(1)}`
        : `L${x(p.t).toFixed(1)},${y(p.low as number).toFixed(1)}`)).join('');
      return `${top}${bottom}Z`;
    }).join('');
  })();

  const inRange = xTicks.filter((t) => t >= t0 && t <= t1);
  const every = Math.max(1, Math.ceil(64 / ((iw / Math.max(1, inRange.length - 1)) || 1)));
  const thinned = inRange.filter((_, i) => i % every === 0);

  const forecastRuns = runs(points, (p) => p.forecast);
  const actualRuns = showActual ? runs(points, (p) => p.actual) : [];

  const indexAt = (clientX: number): number => {
    const r = wrap.current?.getBoundingClientRect();
    if (!r || points.length === 0) return 0;
    const t = t0 + ((clientX - r.left - m.l) / (iw || 1)) * (t1 - t0);
    let lo = 0;
    let hi = points.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if ((points[mid] as TimePoint).t <= t) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  };

  const onPointerMove = (e: PointerEvent) => setActive(indexAt(e.clientX));
  const onKeyDown = (e: KeyboardEvent) => {
    const last = points.length - 1;
    const keys: Record<string, number> = {
      ArrowRight: Math.min(last, (active ?? -1) + 1),
      ArrowLeft: Math.max(0, (active ?? 1) - 1),
      Home: 0,
      End: last,
    };
    if (e.key === 'Escape') return setActive(null);
    const next = keys[e.key];
    if (next === undefined) return;
    e.preventDefault();
    setActive(next);
  };

  const pt = active === null ? null : (points[active] ?? null);
  const px = (p: TimePoint) => (step ? x(p.t) + slotW / 2 : x(p.t));

  const tip = useChartTip(
    wrap, active,
    (i) => {
      const p = points[i];
      if (!p) return null;
      const yy = p.forecast ?? p.actual;
      return { x: px(p), y: yy === null ? m.t + ih / 2 : y(yy) };
    },
    (i) => {
      const p = points[i];
      if (!p) return null;
      const rows: TipRow[] = [{ label: 'Forecast', value: fmtMW(p.forecast), key: 'forecast' }];
      if (showBand) {
        rows.push({
          label: 'Likely range',
          value: p.low === null || p.high === null ? 'no range yet' : `${Math.round(p.low).toLocaleString('en-GB')} to ${fmtMW(p.high)}`,
          key: 'range',
        });
      }
      if (showActual) rows.push({ label: 'Actual', value: fmtMW(p.actual), key: 'actual' });
      const note = tipNote?.(p);
      return { title: tipTitle(p), rows, ...(note ? { note } : {}) };
    },
    [points, showActual, showBand, width, ymax],
  );

  const endLabel = (pick: (p: TimePoint) => number | null) => {
    const last = [...points].reverse().find((p) => pick(p) !== null);
    return last ? y(pick(last) as number) : null;
  };
  const fy = endLabel((p) => p.forecast);
  const ay = showActual ? endLabel((p) => p.actual) : null;
  const closeAndLow = fy !== null && ay !== null && Math.abs(fy - ay) < 14;

  return (
    <div
      ref={wrap}
      className="chart-wrap"
      tabIndex={0}
      role="group"
      aria-label={`${ariaLabel}. Use the left and right arrow keys to read each point.`}
      onPointerMove={onPointerMove}
      onPointerLeave={() => setActive(null)}
      onKeyDown={onKeyDown}
      onFocus={() => setActive((a) => a ?? 0)}
      onBlur={() => setActive(null)}
    >
      {width > 0 && (
        <svg width={width} height={height} role="presentation">
          {yTicks.map((v) => (
            <g key={v}>
              <line className="grid" x1={m.l} x2={m.l + iw} y1={y(v)} y2={y(v)} />
              <text className="axis-label" x={m.l - 8} y={y(v)} dy="0.32em" textAnchor="end">{fmtAxis(v)}</text>
            </g>
          ))}
          <text className="axis-unit" x={0} y={9}>MW</text>
          <line className="baseline" x1={m.l} x2={m.l + iw} y1={y(0)} y2={y(0)} />
          {thinned.map((t) => (
            <text key={t} className="axis-label" x={x(t)} y={height - 8} textAnchor="middle">{xLabel(t)}</text>
          ))}
          {showBand && <path className="band" d={bandPath} />}
          <path className="line-forecast" d={linePath(forecastRuns, (p) => p.forecast)} />
          {showActual && <path className="line-actual" d={linePath(actualRuns, (p) => p.actual)} />}
          {width >= 640 && showActual && fy !== null && (
            <text className="direct-label" x={m.l + iw + 8} y={closeAndLow ? fy - 8 : fy} dy="0.32em">Forecast</text>
          )}
          {width >= 640 && ay !== null && (
            <text className="direct-label" x={m.l + iw + 8} y={closeAndLow ? ay + 8 : ay} dy="0.32em">Actual</text>
          )}
          {pt && (
            <g>
              <line className="crosshair" x1={px(pt)} x2={px(pt)} y1={m.t} y2={m.t + ih} />
              {pt.forecast !== null && <circle className="dot-forecast" cx={px(pt)} cy={y(pt.forecast)} r={4} />}
              {showActual && pt.actual !== null && <circle className="dot-actual" cx={px(pt)} cy={y(pt.actual)} r={4} />}
            </g>
          )}
          <rect x={m.l} y={m.t} width={iw} height={ih} fill="transparent" />
        </svg>
      )}
      <Tooltip tip={tip} />
      <span className="sr-only" aria-live="polite">
        {pt ? `${tipTitle(pt)}. Forecast ${fmtMW(pt.forecast)}.${showActual ? ` Actual ${fmtMW(pt.actual)}.` : ''}` : ''}
      </span>
    </div>
  );
}
