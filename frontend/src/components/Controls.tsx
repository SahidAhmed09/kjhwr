import { useEffect, useState } from 'react';
import { longDayLabel, nextDay } from '../lib/format';

export const CUTOFF_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
const PRESETS = ['09:20', '09:50'];

interface Props {
  day: string;
  first: string;
  last: string;
  onDay: (d: string) => void;
  cutoff: string;
  onCutoff: (c: string) => void;
  updating: boolean;
}

function stepDay(d: string, by: 1 | -1): string {
  if (by === 1) return nextDay(d);
  const x = new Date(`${d}T12:00:00Z`);
  x.setUTCDate(x.getUTCDate() - 1);
  return x.toISOString().slice(0, 10);
}

/** The day being bought on, and the decision time behind a disclosure (the default is right for most uses). */
export function Controls({ day, first, last, onDay, cutoff, onCutoff, updating }: Props) {
  const [draft, setDraft] = useState(cutoff);
  useEffect(() => setDraft(cutoff), [cutoff]);
  const invalid = !CUTOFF_RE.test(draft);

  return (
    <>
      <div className="controls">
        <div className="control">
          <span className="control-label" id="day-label">You are buying on</span>
          <div className="stepper" role="group" aria-labelledby="day-label">
            <button type="button" className="btn icon" aria-label="Previous day" disabled={day <= first}
              onClick={() => onDay(stepDay(day, -1))}>
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M9 2 4 7l5 5" /></svg>
            </button>
            <strong className="stepper-day" aria-live="polite">{longDayLabel(day)}</strong>
            <button type="button" className="btn icon" aria-label="Next day" disabled={day >= last}
              onClick={() => onDay(stepDay(day, 1))}>
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="m5 2 5 5-5 5" /></svg>
            </button>
          </div>
        </div>
        <p className="delivery">
          <span className="control-label">for delivery on</span>
          <strong>{longDayLabel(nextDay(day))}</strong>
        </p>
        <div className="control control-status" role="status" aria-live="polite">
          {updating ? <span className="updating">Updating…</span> : null}
        </div>
      </div>

      <details className="disclosure">
        <summary>Decision time: {cutoff} London time</summary>
        <div className="control">
          <label className="control-label" htmlFor="cutoff">
            The forecast used is the newest one published before this time. Anything published later is ignored.
          </label>
          <div className="cutoff-row">
            <input
              id="cutoff"
              type="time"
              className="field"
              value={draft}
              aria-invalid={invalid}
              aria-describedby={invalid ? 'cutoff-help' : undefined}
              onChange={(e) => {
                setDraft(e.target.value);
                if (CUTOFF_RE.test(e.target.value)) onCutoff(e.target.value);
              }}
            />
            <div className="seg" role="group" aria-label="Common decision times">
              {PRESETS.map((p) => (
                <button key={p} type="button" aria-pressed={cutoff === p} onClick={() => onCutoff(p)}>{p}</button>
              ))}
            </div>
          </div>
          {invalid && <span id="cutoff-help" className="field-error">Enter a time such as 09:20.</span>}
        </div>
      </details>
    </>
  );
}
