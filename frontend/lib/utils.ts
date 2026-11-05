import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format seconds to M:SS display string.
 *
 * @example formatTime(65.7)  → "1:05"
 * @example formatTime(5.23)  → "0:05"
 * @example formatTime(0)     → "0:00"
 */
export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format seconds into MM:SS display string (zero-padded minutes).
 *
 * @example formatDuration(65.7)  → "01:05"
 * @example formatDuration(5.23)  → "00:05"
 * @example formatDuration(600)   → "10:00"
 */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Format a generation duration for display in the editor and Gallery.
 *
 * @example formatGenerationTime(9.4)    → "9s"
 * @example formatGenerationTime(133.2)  → "2m 13s"
 * @example formatGenerationTime(3725)   → "1h 2m"
 */
export function formatGenerationTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  if (total < 60) return `${total}s`;
  const hours = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return secs > 0 ? `${hours}h ${mins}m ${secs}s` : `${hours}h ${mins}m`;
  }
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

/**
 * Format bytes into a human-readable file size string.
 *
 * @example formatFileSize(1024)      → "1.0 KB"
 * @example formatFileSize(13000000)  → "12.4 MB"
 * @example formatFileSize(500)       → "500 B"
 */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
