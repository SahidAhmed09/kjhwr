import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { fmtAxis, linear, niceTicks, useWidth } from './chartUtils';
import { Tooltip, useChartTip, type TipRow } from './Tooltip';

export type Tone = 'over' | 'under' | 'neutral';

export interface BarItem {
  /** Short label for the x axis. */
  label: string;
  tipTitle: string;
  bar: number | null;
  tone: Tone;
  /** Optional second measure drawn as a dot on the same axis. */
  dot?: number | null;
  dotTone?: Tone;
  rows: TipRow[];
  note?: string;
  /** Draw this item with an outline (for example the day currently selected). */
  highlight?: boolean;
}

interface Props {
  items: BarItem[];
  unit: string;
  ariaLabel: string;
  height: number;
  /** Approximate pixels needed by one x label; thins labels to fit. */
  labelWidth?: number;
  /** n + 1 labels placed on the bar edges instead of under the bars (for histograms). */
  edgeLabels?: string[];
}

const MAX_BAR = 24;
const GAP = 2;
const R = 4;

/** Bar from the baseline with a rounded data end and a square base. */
function barPath(cx: number, w: number, y0: number, y1: number): string {
  const x0 = cx - w / 2;
  const x1 = cx + w / 2;
  const r = Math.min(R, w / 2, Math.abs(y1 - y0));
  if (y1 <= y0) {
    return `M${x0},${y0}V${y1 + r}Q${x0},${y1} ${x0 + r},${y1}H${x1 - r}Q${x1},${y1} ${x1},${y1 + r}V${y0}Z`;
  }
  return `M${x0},${y0}V${y1 - r}Q${x0},${y1} ${x0 + r},${y1}H${x1 - r}Q${x1},${y1} ${x1},${y1 - r}V${y0}Z`;
}

export function BarChart({ items, unit, ariaLabel, height, labelWidth = 44, edgeLabels }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const width = useWidth(wrap);
  const [active, setActive] = useState<number | null>(null);

  const narrow = width < 520;
  const m = { l: narrow ? 44 : 56, r: 12, t: 26, b: 30 };
  const iw = Math.max(0, width - m.l - m.r);
  const ih = height - m.t - m.b;
  const n = items.length;
  const band = n ? iw / n : 0;
  const barW = Math.max(2, Math.min(MAX_BAR, band - GAP * 2));

  const vals = items.flatMap((i) => [i.bar, i.dot ?? null]).filter((v): v is number => v !== null);
  const nt = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals), 5);
  const y = linear(nt.lo, nt.hi, m.t + ih, m.t);
  const cxOf = (i: number) => m.l + band * i + band / 2;
  const labelEvery = Math.max(1, Math.ceil(labelWidth / (band || 1)));

  const onPointerMove = (e: PointerEvent) => {
    const r = wrap.current?.getBoundingClientRect();
    if (!r || !n) return;
    const i = Math.floor((e.clientX - r.left - m.l) / (band || 1));
    setActive(Math.max(0, Math.min(n - 1, i)));
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') return setActive(null);
    const next: Record<string, number> = {
      ArrowRight: Math.min(n - 1, (active ?? -1) + 1),
      ArrowLeft: Math.max(0, (active ?? 1) - 1),
      Home: 0,
      End: n - 1,
    };
    const v = next[e.key];
    if (v === undefined) return;
    e.preventDefault();
    setActive(v);
  };

  const cur = active === null ? null : (items[active] ?? null);
  const tip = useChartTip(
    wrap, active,
    (i) => {
      const it = items[i];
      if (!it) return null;
      const v = it.bar ?? it.dot ?? 0;
      return { x: cxOf(i), y: y(v) };
    },
    (i) => {
      const it = items[i];
      return it ? { title: it.tipTitle, rows: it.rows, ...(it.note ? { note: it.note } : {}) } : null;
    },
    [items, width, nt.lo, nt.hi],
  );

  return (
    <div
      ref={wrap}
      className="chart-wrap"
      tabIndex={0}
      role="group"
      aria-label={`${ariaLabel}. Use the left and right arrow keys to read each bar.`}
      onPointerMove={onPointerMove}
      onPointerLeave={() => setActive(null)}
      onKeyDown={onKeyDown}
      onFocus={() => setActive((a) => a ?? 0)}
      onBlur={() => setActive(null)}
    >
      {width > 0 && (
        <svg width={width} height={height} role="presentation">
          {nt.ticks.map((v) => (
            <g key={v}>
              <line className="grid" x1={m.l} x2={m.l + iw} y1={y(v)} y2={y(v)} />
              <text className="axis-label" x={m.l - 8} y={y(v)} dy="0.32em" textAnchor="end">{fmtAxis(v)}</text>
            </g>
          ))}
          <text className="axis-unit" x={0} y={9}>{unit}</text>
          <line className="baseline" x1={m.l} x2={m.l + iw} y1={y(0)} y2={y(0)} />
          {active !== null && <rect className="active-band" x={m.l + band * active} y={m.t} width={band} height={ih} />}
          {items.map((it, i) => (
            <g key={it.tipTitle + i} className={i === active ? 'bar-active' : undefined}>
              {it.bar !== null && it.bar !== 0 && (
                <path
                  className={`mark mark-${it.tone}${it.highlight ? ' mark-selected' : ''}`}
                  d={barPath(cxOf(i), barW, y(0), y(it.bar))}
                />
              )}
              {it.dot !== undefined && it.dot !== null && (
                <circle className={`dot dot-${it.dotTone ?? 'neutral'}`} cx={cxOf(i)} cy={y(it.dot)} r={4} />
              )}
              {!edgeLabels && i % labelEvery === 0 && (
                <text className="axis-label" x={cxOf(i)} y={height - 10} textAnchor="middle">{it.label}</text>
              )}
            </g>
          ))}
          {edgeLabels?.map((t, i) => i % labelEvery === 0 && (
            <text key={t + i} className="axis-label" x={m.l + band * i} y={height - 10} textAnchor="middle">{t}</text>
          ))}
          <rect x={m.l} y={m.t} width={iw} height={ih} fill="transparent" />
        </svg>
      )}
      <Tooltip tip={tip} />
      <span className="sr-only" aria-live="polite">
        {cur ? `${cur.tipTitle}. ${cur.rows.map((r) => `${r.label} ${r.value}`).join('. ')}.` : ''}
      </span>
    </div>
  );
}
