/**
 * Single source of truth for the StoryFlow backend origin.
 *
 * Priority:
 *   1. NEXT_PUBLIC_API_URL (or legacy NEXT_PUBLIC_API_BASE_URL) when set,
 *   2. a previously discovered origin cached in localStorage,
 *   3. http://localhost:8765.
 *
 * When no explicit environment override is configured, the browser probes
 * the usual development origins (`:8765`, then `:8000`) once and validates
 * the response against the StoryFlow `/api/health/` endpoint.  That keeps a
 * frontend started before/independently from the backend working even when
 * Django was launched on a different local port.
 */

export const DEFAULT_API_BASE_URL = 'http://localhost:8765';

const API_ORIGIN_STORAGE_KEY = 'storyflow-api-origin';
const HEALTH_PATH = '/api/health/';
const HEALTH_TIMEOUT_MS = 800;

const EXPLICIT_API_BASE_URL_RAW = (
  process.env.NEXT_PUBLIC_API_URL
  || process.env.NEXT_PUBLIC_API_BASE_URL
  || ''
).trim();
const EXPLICIT_API_BASE_URL = normalizeApiBaseUrl(EXPLICIT_API_BASE_URL_RAW);

let resolvedOrigin: string | null = null;
let discoveryPromise: Promise<string> | null = null;
let lastDiscoveryFailureAt = 0;
const DISCOVERY_RETRY_AFTER_MS = 5000;

/** Remove trailing slashes and whitespace from a configured origin. */
export function normalizeApiBaseUrl(value: string | null | undefined): string {
  const trimmed = (value ?? '').trim();
  if (!trimmed) return DEFAULT_API_BASE_URL;
  return trimmed.replace(/\/+$/, '');
}

/** Absolute URL for an API-relative path (absolute URLs pass through). */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${getApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
}

/** Absolute URL for a backend-relative media path, or null when empty. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return apiUrl(path);
}

/** Read the origin that can be used synchronously for media elements. */
export function getApiBaseUrl(): string {
  if (EXPLICIT_API_BASE_URL_RAW) return EXPLICIT_API_BASE_URL;
  if (resolvedOrigin) return resolvedOrigin;
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage.getItem(API_ORIGIN_STORAGE_KEY);
      if (stored) return normalizeApiBaseUrl(stored);
    } catch {
      // localStorage unavailable — fall through to the default
    }
  }
  return DEFAULT_API_BASE_URL;
}

function rememberOrigin(origin: string): void {
  resolvedOrigin = origin;
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(API_ORIGIN_STORAGE_KEY, origin);
  } catch {
    // localStorage unavailable — in-memory cache is enough
  }
}

async function probeOrigin(origin: string): Promise<boolean> {
  if (typeof fetch === 'undefined') return false;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  try {
    const response = await fetch(`${origin}${HEALTH_PATH}`, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { service?: string; status?: string };
    return data?.service === 'storyflow-backend';
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Resolve the backend origin, discovering it once if it is not configured.
 *
 * Safe to call from every request interceptor: the probe is memoised and
 * concurrent callers share the same promise.
 */
export async function ensureApiBaseUrl(): Promise<string> {
  // An explicit environment value always wins and is never probed away.
  if (EXPLICIT_API_BASE_URL_RAW) return EXPLICIT_API_BASE_URL;
  if (resolvedOrigin) return resolvedOrigin;
  if (discoveryPromise) return discoveryPromise;
  if (typeof window === 'undefined' || process.env.NODE_ENV === 'test') {
    return DEFAULT_API_BASE_URL;
  }
  // Avoid a probe storm when the backend is down: a page can issue many
  // requests at once, so remember a failed sweep for a few seconds.
  if (Date.now() - lastDiscoveryFailureAt < DISCOVERY_RETRY_AFTER_MS) {
    return DEFAULT_API_BASE_URL;
  }

  discoveryPromise = (async () => {
    const candidates = [
      normalizeApiBaseUrl(window.localStorage.getItem(API_ORIGIN_STORAGE_KEY)),
      DEFAULT_API_BASE_URL,
      'http://127.0.0.1:8765',
      'http://localhost:8000',
      'http://127.0.0.1:8000',
    ].filter((value, index, all) => value && all.indexOf(value) === index);

    for (const candidate of candidates) {
      if (await probeOrigin(candidate)) {
        rememberOrigin(candidate);
        lastDiscoveryFailureAt = 0;
        return candidate;
      }
    }
    // Nothing answered: keep the configured default so the caller gets the
    // normal, actionable connection error and discovery can retry later.
    lastDiscoveryFailureAt = Date.now();
    return DEFAULT_API_BASE_URL;
  })().finally(() => {
    discoveryPromise = null;
  });

  return discoveryPromise;
}

export interface ApiHealth {
  ok: boolean;
  baseUrl: string;
  status?: string;
  error?: string;
}

/** Probe the backend health endpoint for UI diagnostics/retry flows. */
export async function checkApiHealth(): Promise<ApiHealth> {
  const baseUrl = await ensureApiBaseUrl();
  try {
    const response = await fetch(`${baseUrl}${HEALTH_PATH}`, {
      method: 'GET',
      cache: 'no-store',
    });
    if (!response.ok) {
      return {
        ok: false,
        baseUrl,
        error: `Health check returned HTTP ${response.status}.`,
      };
    }
    const data = (await response.json()) as { service?: string; status?: string };
    return {
      ok: data?.service === 'storyflow-backend',
      baseUrl,
      status: data?.status,
    };
  } catch {
    return {
      ok: false,
      baseUrl,
      error: 'The backend did not respond.',
    };
  }
}

/** Forget a discovered origin (used by retry when the backend moved). */
export function resetApiBaseUrlDiscovery(): void {
  resolvedOrigin = null;
  discoveryPromise = null;
  lastDiscoveryFailureAt = 0;
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(API_ORIGIN_STORAGE_KEY);
  } catch {
    // ignore
  }
}
