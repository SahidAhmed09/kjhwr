import type { ApiError } from '../api/client';

export function Loading({ what }: { what: string }) {
  return (
    <div className="status loading" role="status" aria-busy="true">
      <span className="bar" />
      <span className="bar short" />
      <span className="sr-only">Loading {what}</span>
    </div>
  );
}

const HINT: Record<number, string> = {
  0: 'Check that the back end is running, then try again.',
  404: 'Choose a day inside the data window.',
  422: 'Check the decision time and day, then try again.',
  503: 'The data snapshot is not available on the server. Rebuild it with python backend/scripts/fetch_snapshot.py.',
};

export function ErrorNote({ error, what, onRetry }: { error: ApiError; what: string; onRetry: () => void }) {
  return (
    <div className="status error" role="alert">
      <p><strong>Could not load {what}.</strong> {error.message}</p>
      <p className="muted">{HINT[error.status] ?? 'Try again in a moment.'}</p>
      <button type="button" className="btn" onClick={onRetry}>Try again</button>
    </div>
  );
}
