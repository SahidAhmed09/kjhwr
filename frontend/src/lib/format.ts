const LONDON = 'Europe/London';
const MINUS = '−';
const NBSP = '\u00a0';

const int = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });

export function fmtInt(n: number): string {
  return int.format(n).replace('-', MINUS);
}

export function fmtMW(n: number | null): string {
  return n === null ? 'no data' : `${fmtInt(n)}${NBSP}MW`;
}

export function fmtSignedMW(n: number | null): string {
  if (n === null) return 'no data';
  const r = Math.round(n);
  return `${r > 0 ? '+' : ''}${fmtInt(r)}${NBSP}MW`;
}

export function fmtGW(mw: number, digits = 1): string {
  return `${(mw / 1000).toFixed(digits).replace('-', MINUS)}${NBSP}GW`;
}

export function fmtMWh(n: number): string {
  return `${fmtInt(n)}${NBSP}MWh`;
}

export function fmtPct(frac: number | null, digits = 0): string {
  return frac === null ? 'no data' : `${(frac * 100).toFixed(digits)}%`;
}

/** "09:20" in London wall-clock time from an ISO string or epoch milliseconds. */
export function londonTime(instant: string | number): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: LONDON, hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(instant));
}

/** "Wed 14 Jan" in London time from an ISO instant. */
export function londonDayOfInstant(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: LONDON, weekday: 'short', day: 'numeric', month: 'short',
  }).format(new Date(iso)).replace(',', '');
}

/** "Thu 15 Jan" from a plain calendar date (YYYY-MM-DD). */
export function dayLabel(isoDate: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short',
  }).format(new Date(`${isoDate}T12:00:00Z`)).replace(',', '');
}

/** "Thursday 15 January" from a plain calendar date. */
export function longDayLabel(isoDate: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long',
  }).format(new Date(`${isoDate}T12:00:00Z`)).replace(',', '');
}

/** "1 h 50 min", "40 min", "2 h". */
export function fmtDuration(minutes: number): string {
  const m = Math.round(minutes);
  const h = Math.floor(m / 60);
  const r = m % 60;
  if (h === 0) return `${r} min`;
  return r === 0 ? `${h} h` : `${h} h ${r} min`;
}

/** "15 Jan" from a plain calendar date. */
export function shortDay(isoDate: string): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short' })
    .format(new Date(`${isoDate}T12:00:00Z`));
}

/** The calendar date after `isoDate`. */
export function nextDay(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

/** Every calendar date from `first` to `last` inclusive. */
export function dateRange(first: string, last: string): string[] {
  const out: string[] = [];
  for (let d = first; d <= last; d = nextDay(d)) out.push(d);
  return out;
}

/** "15 Jan" in London time from epoch milliseconds. */
export function londonShortDay(ms: number): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: LONDON, day: 'numeric', month: 'short' }).format(new Date(ms));
}

/** Signed whole number with a true minus sign and no unit, for table columns. */
export function fmtSigned(n: number | null): string {
  if (n === null) return 'no data';
  const r = Math.round(n);
  return `${r > 0 ? '+' : ''}${fmtInt(r)}`;
}
