export type GlyphKind =
  | 'forecast'
  | 'actual'
  | 'range'
  | 'over'
  | 'under'
  | 'neutral'
  | 'dot-over'
  | 'dot-under'
  | 'dot-neutral';

/** Small key that mirrors the mark it names. Used by legends and tooltips. */
export function KeyGlyph({ kind }: { kind: GlyphKind }) {
  return (
    <svg className={`glyph glyph-${kind}`} width="18" height="12" viewBox="0 0 18 12" aria-hidden="true">
      {kind === 'forecast' && <line x1="1" y1="6" x2="17" y2="6" />}
      {kind === 'actual' && <line x1="1" y1="6" x2="17" y2="6" strokeDasharray="4 3" />}
      {kind === 'range' && <rect x="1" y="1" width="16" height="10" rx="1" />}
      {(kind === 'over' || kind === 'under' || kind === 'neutral') && <rect x="3" y="1" width="12" height="10" rx="2" />}
      {kind.startsWith('dot-') && <circle cx="9" cy="6" r="4" />}
    </svg>
  );
}
