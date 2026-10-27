import { useLayoutEffect, useState, type RefObject } from 'react';

export type Scale = (v: number) => number;

export function linear(d0: number, d1: number, r0: number, r1: number): Scale {
  const span = d1 - d0 || 1;
  return (v) => r0 + ((v - d0) / span) * (r1 - r0);
}

function niceStep(raw: number): number {
  const exp = Math.floor(Math.log10(raw));
  const f = raw / 10 ** exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * 10 ** exp;
}

/** Round-number axis ticks covering [min, max]. */
export function niceTicks(min: number, max: number, target = 5): { ticks: number[]; lo: number; hi: number } {
  if (min === max) max = min + 1;
  const step = niceStep((max - min) / target);
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  return { ticks, lo, hi };
}

/** Width in CSS pixels of an element, kept in sync with its size. */
export function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

/** Axis tick labels: 0, 5,000, 10,000 -> compact above 9,999 only when it stays exact. */
export function fmtAxis(v: number): string {
  const a = Math.abs(v);
  const sign = v < 0 ? '−' : '';
  if (a >= 1000 && a % 1000 === 0) return `${sign}${a / 1000}K`;
  return `${sign}${a.toLocaleString('en-GB')}`;
}
