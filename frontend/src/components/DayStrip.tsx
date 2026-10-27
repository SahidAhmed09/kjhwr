import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import type { DayRow } from '../api/types';
import { Tooltip, type TipState } from '../charts/Tooltip';
import { dayLabel, fmtSignedMW, fmtMW, nextDay } from '../lib/format';

interface Props {
  /** Decision dates, in order. */
  days: string[];
  /** Accuracy rows keyed by delivery date. */
  byDelivery: Map<string, DayRow>;
  selected: string;
  onSelect: (day: string) => void;
}

const BAR_AREA = 52;
const HALF = BAR_AREA / 2;
const BAR_W = 16;
const R = 4;

function stripBar(h: number, up: boolean): string {
  if (h <= 0) return '';
  const x0 = (40 - BAR_W) / 2;
  const x1 = x0 + BAR_W;
  const r = Math.min(R, h);
  return up
    ? `M${x0},${HALF}V${HALF - h + r}Q${x0},${HALF - h} ${x0 + r},${HALF - h}H${x1 - r}Q${x1},${HALF - h} ${x1},${HALF - h + r}V${HALF}Z`
    : `M${x0},${HALF}V${HALF + h - r}Q${x0},${HALF + h} ${x0 + r},${HALF + h}H${x1 - r}Q${x1},${HALF + h} ${x1},${HALF + h - r}V${HALF}Z`;
}

/** One tile per decision date. Bar height is that day's average error; red is over-forecast, blue under. */
export function DayStrip({ days, byDelivery, selected, onSelect }: Props) {
  const group = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<TipState | null>(null);

  const rows = days.map((d) => byDelivery.get(nextDay(d)));
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r?.bias ?? 0)));

  useEffect(() => {
    group.current?.querySelector<HTMLElement>('[aria-pressed="true"]')
      ?.scrollIntoView({ block: 'nearest', inline: 'center' });
  }, [selected]);

  const show = (el: HTMLElement, day: string, row: DayRow | undefined) => {
    const r = el.getBoundingClientRect();
    const rows = row && row.bias !== null
      ? [
        { label: row.bias > 0 ? 'Forecast too high on average' : 'Forecast too low on average',
          value: fmtSignedMW(row.bias), key: (row.bias > 0 ? 'over' : 'under') as 'over' | 'under' },
        { label: 'Typical miss', value: fmtMW(row.mae), key: 'dot-neutral' as const },
      ]
      : [{ label: 'Error', value: 'no data' }];
    setTip({
      title: `Buy ${dayLabel(day)} for ${dayLabel(nextDay(day))}`,
      rows,
      ...(row ? { note: `${row.n} of ${row.n_slots} half-hours scored` } : {}),
      x: r.right,
      y: r.top + r.height / 2,
    });
  };

  const onKeyDown = (e: KeyboardEvent) => {
    const i = days.indexOf(selected);
    const target: Record<string, number> = {
      ArrowRight: Math.min(days.length - 1, i + 1),
      ArrowLeft: Math.max(0, i - 1),
      Home: 0,
      End: days.length - 1,
    };
    const t = target[e.key];
    if (t === undefined) return;
    e.preventDefault();
    const day = days[t] as string;
    onSelect(day);
    requestAnimationFrame(() => group.current?.querySelector<HTMLElement>(`[data-day="${day}"]`)?.focus());
  };

  return (
    <div className="strip" role="group" aria-label="Choose the day you are buying on. Each bar shows how far off the forecast for the next day turned out to be.">
      <div className="strip-scroll" ref={group} onKeyDown={onKeyDown} onScroll={() => setTip(null)}>
        {days.map((d, k) => {
          const row = rows[k];
          const bias = row?.bias ?? null;
          const h = bias === null ? 0 : Math.round((Math.abs(bias) / maxAbs) * (HALF - 2));
          const up = (bias ?? 0) > 0;
          const date = new Date(`${d}T12:00:00Z`);
          const weekday = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', weekday: 'narrow' }).format(date);
          return (
            <button
              key={d}
              type="button"
              className={`tile${d === selected ? ' tile-selected' : ''}`}
              data-day={d}
              aria-pressed={d === selected}
              aria-label={`${dayLabel(d)}, buying for ${dayLabel(nextDay(d))}. ${bias === null ? 'No error figure.' : `Forecast ${up ? 'too high' : 'too low'} by ${fmtSignedMW(Math.abs(bias))} on average.`}`}
              tabIndex={d === selected ? 0 : -1}
              onClick={() => onSelect(d)}
              onPointerEnter={(e) => show(e.currentTarget, d, row)}
              onPointerLeave={() => setTip(null)}
              onFocus={(e) => show(e.currentTarget, d, row)}
              onBlur={() => setTip(null)}
            >
              <svg viewBox={`0 0 40 ${BAR_AREA}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
                <line className="baseline" x1="0" x2="40" y1={HALF} y2={HALF} />
                {bias === null
                  ? <circle className="dot dot-neutral" cx="20" cy={HALF} r="2.5" />
                  : <path className={`mark ${up ? 'mark-over' : 'mark-under'}`} d={stripBar(h, up)} />}
              </svg>
              <span className="tile-num num">{date.getUTCDate()}</span>
              <span className="tile-wd">{weekday}</span>
            </button>
          );
        })}
      </div>
      <Tooltip tip={tip} />
    </div>
  );
}
