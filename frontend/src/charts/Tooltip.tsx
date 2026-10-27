import { useLayoutEffect, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { KeyGlyph, type GlyphKind } from './KeyGlyph';

export interface TipRow {
  label: string;
  value: string;
  key?: GlyphKind;
}

export interface TipContent {
  title: string;
  rows: TipRow[];
  note?: string;
}

export interface TipState extends TipContent {
  /** Anchor in viewport coordinates. */
  x: number;
  y: number;
}

const GAP = 12;
const EDGE = 8;

export function Tooltip({ tip }: { tip: TipState | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: 0, top: 0 });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!tip || !el) return;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    let left = tip.x + GAP;
    if (left + w > window.innerWidth - EDGE) left = tip.x - GAP - w;
    left = Math.max(EDGE, Math.min(left, window.innerWidth - EDGE - w));
    let top = tip.y - h / 2;
    top = Math.max(EDGE, Math.min(top, window.innerHeight - EDGE - h));
    setPos({ left, top });
  }, [tip]);

  if (!tip) return null;
  return createPortal(
    <div className="tip" ref={ref} style={{ left: pos.left, top: pos.top }} role="presentation">
      <div className="tip-title">{tip.title}</div>
      {tip.rows.map((r) => (
        <div className="tip-row" key={r.label}>
          <span className="tip-key">{r.key ? <KeyGlyph kind={r.key} /> : null}</span>
          <span className="tip-value num">{r.value}</span>
          <span className="tip-label">{r.label}</span>
        </div>
      ))}
      {tip.note ? <div className="tip-note">{tip.note}</div> : null}
    </div>,
    document.body,
  );
}

/**
 * Turns the active mark of a chart into a viewport-anchored tooltip.
 * `anchor` returns a point relative to `wrapRef`'s top-left; `content` returns the text.
 * The tooltip clears on scroll or resize so it never floats away from its mark.
 */
export function useChartTip(
  wrapRef: RefObject<HTMLElement | null>,
  active: number | null,
  anchor: (i: number) => { x: number; y: number } | null,
  content: (i: number) => TipContent | null,
  deps: readonly unknown[],
): TipState | null {
  const [tip, setTip] = useState<TipState | null>(null);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (active === null || !el) {
      setTip(null);
      return;
    }
    const a = anchor(active);
    const c = content(active);
    if (!a || !c) {
      setTip(null);
      return;
    }
    const r = el.getBoundingClientRect();
    setTip({ ...c, x: r.left + a.x, y: r.top + a.y });
    const clear = () => setTip(null);
    window.addEventListener('scroll', clear, { passive: true, capture: true });
    window.addEventListener('resize', clear);
    return () => {
      window.removeEventListener('scroll', clear, true);
      window.removeEventListener('resize', clear);
    };
    // anchor/content are recreated every render; the caller lists what they actually depend on in `deps`.
  }, [active, wrapRef, ...deps]);

  return tip;
}
