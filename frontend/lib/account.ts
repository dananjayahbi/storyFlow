/**
 * Account context helpers.
 *
 * Each workspace section (Facebook / YouTube) can contain many accounts
 * (pages / channels).  The selected account is kept in localStorage per
 * section and can also be pinned in the URL with `?account=<uuid>` so links
 * are shareable and browser navigation stays predictable.
 */

import type { Section } from './section';

const STORAGE_PREFIX = 'storyflow-account-';
const STORAGE_NAME_PREFIX = 'storyflow-account-name-';

function storageKey(section: Section): string {
  return `${STORAGE_PREFIX}${section}`;
}

export function getStoredAccountId(section: Section): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(storageKey(section));
  } catch {
    return null;
  }
}

export function getStoredAccountName(section: Section): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(`${STORAGE_NAME_PREFIX}${section}`);
  } catch {
    return null;
  }
}

export function setStoredAccount(
  section: Section,
  accountId: string,
  accountName?: string,
): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(storageKey(section), accountId);
    if (accountName) {
      localStorage.setItem(`${STORAGE_NAME_PREFIX}${section}`, accountName);
    }
  } catch {
    // localStorage may be unavailable (private mode); the URL still works.
  }
}

export function clearStoredAccount(section: Section): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(storageKey(section));
    localStorage.removeItem(`${STORAGE_NAME_PREFIX}${section}`);
  } catch {
    // ignore
  }
}

/** Account id from the current URL, falling back to the stored selection. */
export function getCurrentAccountId(section?: Section): string | null {
  if (typeof window === 'undefined') return null;

  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get('account');
  if (fromUrl) return fromUrl;

  if (!section) {
    const path = window.location.pathname;
    section = path.startsWith('/youtube') ? 'youtube' : 'facebook';
  }
  return getStoredAccountId(section);
}

/** Append the active account id to a path, preserving existing params. */
export function withAccount(path: string, accountId?: string | null): string {
  const id = accountId ?? getCurrentAccountId();
  if (!id) return path;
  const [base, query = ''] = path.split('?');
  const params = new URLSearchParams(query);
  if (!params.get('account')) params.set('account', id);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}
