import { useEffect, useState } from 'react';

export type View = 'decision' | 'accuracy';

interface Props {
  view: View;
  onView: (v: View) => void;
}

type Theme = 'light' | 'dark';

function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage can be blocked; the choice then lasts for this visit only */
  }
}

function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function Masthead({ view, onView }: Props) {
  const [theme, setTheme] = useState<Theme>(() => (readPref('theme') as Theme | null) ?? systemTheme());
  const [patterns, setPatterns] = useState(() => readPref('patterns') === 'on');

  useEffect(() => {
    document.documentElement.dataset['theme'] = theme;
  }, [theme]);
  useEffect(() => {
    document.documentElement.dataset['patterns'] = patterns ? 'on' : 'off';
  }, [patterns]);

  return (
    <header className="masthead">
      <div className="masthead-top">
        <div className="brand">
          <h1>Wind day-ahead</h1>
          <p className="muted">Helps the day-ahead buying team decide how much wind to count on for tomorrow, and how far to trust the forecast. Great Britain, January 2026 replay.</p>
        </div>
        <div className="prefs">
          <button type="button" className="btn-text" aria-pressed={theme === 'dark'}
            onClick={() => { const t = theme === 'dark' ? 'light' : 'dark'; setTheme(t); writePref('theme', t); }}>
            Dark mode
          </button>
          <button type="button" className="btn-text" aria-pressed={patterns}
            onClick={() => { setPatterns(!patterns); writePref('patterns', !patterns ? 'on' : 'off'); }}>
            Patterns
          </button>
        </div>
      </div>
      <nav className="views" aria-label="Views">
        <button type="button" aria-current={view === 'decision' ? 'page' : undefined} onClick={() => onView('decision')}>
          Tomorrow&rsquo;s wind
        </button>
        <button type="button" aria-current={view === 'accuracy' ? 'page' : undefined} onClick={() => onView('accuracy')}>
          Track record
        </button>
      </nav>
    </header>
  );
}
