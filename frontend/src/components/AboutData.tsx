import type { MetaResponse } from '../api/types';
import { dayLabel, fmtInt } from '../lib/format';

/** The data's provenance and known limits, kept one click away on every view. */
export function AboutData({ meta }: { meta: MetaResponse }) {
  const d = meta.data;
  return (
    <details className="about">
      <summary>About these numbers</summary>
      <ul>
        {meta.notes.map((n) => <li key={n}>{n}</li>)}
        <li>
          Error is forecast minus actual, so a positive error means the forecast was too high.
          Times are London time; the data behind them is stored in UTC.
        </li>
      </ul>
      <p className="muted">
        Source: Elexon BMRS (FUELHH actuals, WINDFOR forecasts), national GB wind only. Snapshot fetched{' '}
        {dayLabel(d.fetched_at.slice(0, 10))} {d.fetched_at.slice(0, 4)}; {fmtInt(d.n_forecast_rows)} forecast rows from{' '}
        {fmtInt(d.n_publish_times)} publishes and {fmtInt(d.n_actual_rows)} half-hourly actuals. File checksum{' '}
        <span className="num">{d.sha256.slice(0, 12)}</span>.
      </p>
    </details>
  );
}
