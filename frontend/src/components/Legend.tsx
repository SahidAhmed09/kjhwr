import { KeyGlyph, type GlyphKind } from '../charts/KeyGlyph';

export interface LegendItem {
  kind: GlyphKind;
  label: string;
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label}>
          <KeyGlyph kind={i.kind} />
          <span>{i.label}</span>
        </li>
      ))}
    </ul>
  );
}
