/**
 * Section helpers.
 *
 * StoryFlow has two completely independent workspaces: Facebook Reels and
 * YouTube Videos.  Every page lives under `/{section}/...` and every API
 * request is scoped to the section encoded in the URL, so data can never
 * leak from one side to the other.
 */

export type Section = 'facebook' | 'youtube';

export const SECTIONS: Section[] = ['facebook', 'youtube'];

export const SECTION_LABELS: Record<Section, string> = {
  facebook: 'Facebook Reels',
  youtube: 'YouTube Videos',
};

/** Resolve the active section from a pathname (`/youtube/...` → youtube). */
export function sectionFromPathname(pathname: string | null | undefined): Section {
  return pathname?.startsWith('/youtube') ? 'youtube' : 'facebook';
}

/**
 * Resolve the active section in the browser. Used by API helpers so every
 * request carries the correct section even when a page does not pass it
 * explicitly.
 */
export function getCurrentSection(): Section {
  if (typeof window === 'undefined') return 'facebook';
  return sectionFromPathname(window.location.pathname);
}

/** Build a section-scoped path, e.g. sectionPath('youtube', '/projects'). */
export function sectionPath(section: Section, path = ''): string {
  const suffix = path && path !== '/' ? (path.startsWith('/') ? path : `/${path}`) : '';
  return `/${section}${suffix}`;
}

/** Prefix a legacy root-level app path with the active section. */
export function scopedHref(pathname: string, path: string): string {
  return sectionPath(sectionFromPathname(pathname), path);
}
