import { KeyGlyph } from '../charts/KeyGlyph';

/** Says once, in words, what the two error colours mean. Shown with the day strip, where the colours first appear. */
export function ColourKey() {
  return (
    <p className="colour-key">
      <span className="key-item"><KeyGlyph kind="over" /><strong>Red means over-forecast:</strong></span>{' '}
      too high, so the wind you counted on did not arrive and you bought too little. This is the costly side.{' '}
      <span className="key-item"><KeyGlyph kind="under" /><strong>Blue means under-forecast:</strong></span>{' '}
      too low.
    </p>
  );
}
