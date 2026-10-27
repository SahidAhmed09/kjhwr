import { useEffect, useMemo, useState } from 'react';
import type { AccuracyResponse, DecisionResponse, MetaResponse, SeriesResponse } from './api/types';
import { useApi } from './api/useApi';
import { ColourKey } from './components/ColourKey';
import { Controls, CUTOFF_RE } from './components/Controls';
import { DayStrip } from './components/DayStrip';
import { Masthead, type View } from './components/Masthead';
import { ErrorNote, Loading } from './components/Status';
import { dateRange } from './lib/format';
import { AccuracyView } from './views/AccuracyView';
import { DecisionView } from './views/DecisionView';

const DEFAULT_CUTOFF = '09:20';

interface UrlState {
  view: View;
  day: string | null;
  cutoff: string;
}

function readUrl(): UrlState {
  const q = new URLSearchParams(window.location.search);
  const cutoff = q.get('cutoff') ?? DEFAULT_CUTOFF;
  return {
    view: q.get('view') === 'accuracy' ? 'accuracy' : 'decision',
    day: q.get('day'),
    cutoff: CUTOFF_RE.test(cutoff) ? cutoff : DEFAULT_CUTOFF,
  };
}

export function App() {
  const initial = useMemo(readUrl, []);
  const [view, setView] = useState<View>(initial.view);
  const [cutoff, setCutoff] = useState(initial.cutoff);
  const [requestedDay, setRequestedDay] = useState<string | null>(initial.day);
  const [jumpOpen, setJumpOpen] = useState(false);

  const meta = useApi<MetaResponse>('/api/meta');
  const first = meta.data?.decision_window.first;
  const last = meta.data?.decision_window.last;
  const days = useMemo(() => (first && last ? dateRange(first, last) : []), [first, last]);
  // An unknown or out-of-window day in the URL falls back to the last day of the window.
  const day = requestedDay && days.includes(requestedDay) ? requestedDay : (last ?? '');

  const q = encodeURIComponent(cutoff);
  const accuracy = useApi<AccuracyResponse>(first ? `/api/accuracy?cutoff=${q}` : null);
  const decision = useApi<DecisionResponse>(first && view === 'decision' ? `/api/decision?decision_date=${day}&cutoff=${q}` : null);
  const series = useApi<SeriesResponse>(first && view === 'accuracy' ? `/api/series?cutoff=${q}` : null);

  useEffect(() => {
    if (!first) return;
    const p = new URLSearchParams({ view, day, cutoff });
    window.history.replaceState(null, '', `?${p.toString()}`);
  }, [view, day, cutoff, first]);

  const byDelivery = useMemo(() => new Map((accuracy.data?.by_day ?? []).map((r) => [r.key, r])), [accuracy.data]);
  const updating = accuracy.loading || decision.loading || series.loading;

  return (
    <div className="sheet">
      <Masthead view={view} onView={setView} />
      {!meta.data ? (
        meta.error
          ? <ErrorNote error={meta.error} what="the data summary" onRetry={meta.retry} />
          : <Loading what="the data summary" />
      ) : (
        <main>
          <div className="toolbar">
            <Controls
              day={day}
              first={meta.data.decision_window.first}
              last={meta.data.decision_window.last}
              onDay={setRequestedDay}
              cutoff={cutoff}
              onCutoff={setCutoff}
              updating={updating}
            />
            <details className="disclosure" onToggle={(e) => setJumpOpen(e.currentTarget.open)}>
              <summary>Jump to another day</summary>
              {jumpOpen && (
                <>
                  <DayStrip days={days} byDelivery={byDelivery} selected={day} onSelect={setRequestedDay} />
                  <ColourKey />
                </>
              )}
            </details>
          </div>
          {view === 'decision'
            ? <DecisionView decision={decision} meta={meta.data} onSeeTrackRecord={() => { setView('accuracy'); window.scrollTo({ top: 0 }); }} />
            : <AccuracyView accuracy={accuracy} series={series} meta={meta.data} day={day} />}
        </main>
      )}
      <PatternDefs />
    </div>
  );
}

/** Hatch fills for the optional patterns mode. Direction matches the sign: over leans right, under leans left. */
function PatternDefs() {
  return (
    <svg width="0" height="0" className="pattern-defs" aria-hidden="true" focusable="false">
      <defs>
        <pattern id="hatch-over" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" className="hatch-bg-over" />
          <line x1="0" y1="0" x2="0" y2="6" className="hatch-ink" strokeWidth="2.4" />
        </pattern>
        <pattern id="hatch-under" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(135)">
          <rect width="6" height="6" className="hatch-bg-under" />
          <line x1="0" y1="0" x2="0" y2="6" className="hatch-ink" strokeWidth="2.4" />
        </pattern>
      </defs>
    </svg>
  );
}
