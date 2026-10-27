import { useCallback, useEffect, useReducer, useState } from 'react';
import { ApiError, getJson } from './client';

export interface ApiState<T> {
  /** Last successful response. Kept on screen while a new request is in flight or has failed. */
  data: T | null;
  /** Which request `data` belongs to. */
  dataPath: string | null;
  error: ApiError | null;
  loading: boolean;
}

type Action<T> =
  | { type: 'start' }
  | { type: 'ok'; path: string; data: T }
  | { type: 'fail'; error: ApiError };

function reducer<T>(state: ApiState<T>, action: Action<T>): ApiState<T> {
  switch (action.type) {
    case 'start':
      return { ...state, loading: true, error: null };
    case 'ok':
      return { data: action.data, dataPath: action.path, error: null, loading: false };
    case 'fail':
      return { ...state, error: action.error, loading: false };
  }
}

export type ApiResult<T> = ApiState<T> & {
  /** True when `data` belongs to an earlier request than the current path. */
  stale: boolean;
  retry: () => void;
};

/** GET `path` as JSON. Previous data stays available while the next request runs. */
export function useApi<T>(path: string | null): ApiResult<T> {
  const [state, dispatch] = useReducer(
    reducer as (s: ApiState<T>, a: Action<T>) => ApiState<T>,
    { data: null, dataPath: null, error: null, loading: path !== null },
  );
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);

  useEffect(() => {
    if (path === null) return;
    const ctl = new AbortController();
    dispatch({ type: 'start' });
    getJson<T>(path, ctl.signal)
      .then((data) => dispatch({ type: 'ok', path, data }))
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        dispatch({ type: 'fail', error: e instanceof ApiError ? e : new ApiError(0, String(e)) });
      });
    return () => ctl.abort();
  }, [path, attempt]);

  return { ...state, stale: state.data !== null && state.dataPath !== path, retry };
}
