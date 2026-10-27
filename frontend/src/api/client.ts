export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface ValidationItem {
  loc?: unknown[];
  msg?: string;
}

function detailText(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
      return (d as ValidationItem[])
        .map((i) => `${(i.loc ?? []).slice(1).join('.')}: ${i.msg ?? 'invalid'}`)
        .join('; ');
    }
  }
  return `The server answered with status ${status}.`;
}

/** Empty means same origin (local, Docker, single Vercel project). A separate front end sets VITE_API_BASE at build time. */
const API_BASE = ((import.meta.env.VITE_API_BASE as string | undefined) ?? '').replace(/\/+$/, '');

export async function getJson<T>(path: string, signal: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { signal, headers: { Accept: 'application/json' } });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ApiError(0, 'Cannot reach the server. Check that the back end is running.');
  }
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailText(body, res.status));
  return body as T;
}
