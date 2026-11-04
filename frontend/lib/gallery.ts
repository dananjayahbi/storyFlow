import type { GalleryItem, RenderingStatus } from './types';

export const GALLERY_STATUS_OPTIONS: Array<{
  value: RenderingStatus;
  label: string;
  hint: string;
}> = [
  {
    value: 'rendered',
    label: 'Rendered',
    hint: 'Freshly exported, not prepared for publishing yet',
  },
  {
    value: 'ready_to_publish',
    label: 'Ready to publish',
    hint: 'Reviewed and approved for the next upload',
  },
  {
    value: 'published',
    label: 'Published',
    hint: 'Already published to the account audience',
  },
];

export function galleryStatusMeta(status: RenderingStatus | string) {
  switch (status) {
    case 'ready_to_publish':
      return {
        label: 'Ready to publish',
        dot: 'bg-amber-500',
        badge:
          'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300',
      };
    case 'published':
      return {
        label: 'Published',
        dot: 'bg-emerald-500',
        badge:
          'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
      };
    default:
      return {
        label: 'Rendered',
        dot: 'bg-sky-500',
        badge:
          'border-sky-500/30 bg-sky-500/15 text-sky-700 dark:text-sky-300',
      };
  }
}

export function formatGalleryFileSize(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const size = bytes / Math.pow(1024, index);
  return `${size.toFixed(index > 0 ? 1 : 0)} ${units[index]}`;
}

export function formatGalleryRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMonth = Math.floor(diffDay / 30);
  if (diffMonth < 12) return `${diffMonth}mo ago`;
  return `${Math.floor(diffDay / 365)}y ago`;
}

/** Filter a gallery list client-side (used by the Gallery filter bar). */
export function filterGalleryItems(
  items: GalleryItem[],
  filters: {
    status?: RenderingStatus | 'all';
    project?: string;
    query?: string;
    sort?: 'newest' | 'oldest';
  },
): GalleryItem[] {
  const query = (filters.query ?? '').trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (filters.status && filters.status !== 'all' && item.status !== filters.status) {
      return false;
    }
    if (filters.project && filters.project !== 'all' && item.project_id !== filters.project) {
      return false;
    }
    if (query) {
      const haystack = `${item.title} ${item.project_title}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });

  return filtered.sort((a, b) => {
    const left = new Date(a.created_at).getTime();
    const right = new Date(b.created_at).getTime();
    return filters.sort === 'oldest' ? left - right : right - left;
  });
}
