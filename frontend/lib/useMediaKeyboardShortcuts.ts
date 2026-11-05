'use client';

import type { RefObject } from 'react';
import { useEffect } from 'react';

/**
 * Options for {@link useMediaKeyboardShortcuts}.
 *
 * Every callback is optional. When a callback is omitted the hook updates the
 * underlying media element directly, which keeps it usable in both small
 * inline players and full-featured dialogs.
 */
export interface MediaKeyboardShortcutOptions {
  /** Seconds skipped by an arrow key. Shift doubles this. Defaults to 5. */
  seekStep?: number;
  /** Volume change for an up/down arrow key (0..1). Defaults to 0.1. */
  volumeStep?: number;
  /** Disable the shortcuts while the media is loading or broken. */
  enabled?: boolean;
  onTogglePlay?: () => void;
  onSkip?: (seconds: number) => void;
  onSeekTo?: (time: number) => void;
  onVolumeChange?: (volume: number) => void;
  onToggleMute?: () => void;
  onToggleFullscreen?: () => void;
}

const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);
const INTERACTIVE_TAGS = new Set(['BUTTON', 'A']);

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return TYPING_TAGS.has(target.tagName);
}

function clampVolume(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/**
 * Add standard media keyboard shortcuts to a custom player.
 *
 * | Key | Action |
 * |-----|--------|
 * | Space / K | Play or pause |
 * | ← / → | Seek back / forward (Shift = double step) |
 * | J / L | Seek back / forward by two steps |
 * | ↑ / ↓ | Volume up / down |
 * | M | Mute / unmute |
 * | Home / End | Jump to the start / end |
 * | F | Toggle fullscreen (video only) |
 *
 * The listener is scoped to ``containerRef`` when one is supplied, so several
 * inline players can coexist on a page. Pass ``null`` to attach to the
 * document while a modal player is open. Typing fields and interactive
 * controls keep their native keyboard behaviour.
 */
export function useMediaKeyboardShortcuts(
  containerRef: RefObject<HTMLElement | null> | null,
  mediaRef: RefObject<HTMLMediaElement | null>,
  {
    seekStep = 5,
    volumeStep = 0.1,
    enabled = true,
    onTogglePlay,
    onSkip,
    onSeekTo,
    onVolumeChange,
    onToggleMute,
    onToggleFullscreen,
  }: MediaKeyboardShortcutOptions = {},
) {
  useEffect(() => {
    if (!enabled) return;
    const container: EventTarget | null = containerRef
      ? containerRef.current
      : typeof document !== 'undefined'
        ? document
        : null;
    if (!container) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const media = mediaRef.current;
      if (!media) return;

      const target = event.target as HTMLElement | null;
      if (isTypingTarget(target)) return;
      // Let a focused button/link handle Space/Enter itself (for example the
      // play button), but still allow the other media shortcuts to bubble.
      const interactive = target ? INTERACTIVE_TAGS.has(target.tagName) : false;

      const key = event.key;
      if (interactive && (key === ' ' || key === 'Spacebar' || key === 'Enter')) {
        return;
      }
      const step = event.shiftKey ? seekStep * 2 : seekStep;
      let handled = true;

      switch (key) {
        case ' ':
        case 'Spacebar':
          if (onTogglePlay) onTogglePlay();
          else if (media.paused) void media.play();
          else media.pause();
          break;

        case 'k':
        case 'K':
          if (onTogglePlay) onTogglePlay();
          else if (media.paused) void media.play();
          else media.pause();
          break;

        case 'ArrowLeft':
          if (onSkip) onSkip(-step);
          else {
            const max = Number.isFinite(media.duration)
              ? media.duration
              : Number.POSITIVE_INFINITY;
            media.currentTime = Math.max(
              0,
              Math.min(max, media.currentTime - step),
            );
          }
          break;

        case 'ArrowRight':
          if (onSkip) onSkip(step);
          else {
            const max = Number.isFinite(media.duration)
              ? media.duration
              : Number.POSITIVE_INFINITY;
            media.currentTime = Math.max(
              0,
              Math.min(max, media.currentTime + step),
            );
          }
          break;

        case 'j':
        case 'J':
          if (onSkip) onSkip(-step * 2);
          else {
            const max = Number.isFinite(media.duration)
              ? media.duration
              : Number.POSITIVE_INFINITY;
            media.currentTime = Math.max(
              0,
              Math.min(max, media.currentTime - step * 2),
            );
          }
          break;

        case 'l':
        case 'L':
          if (onSkip) onSkip(step * 2);
          else {
            const max = Number.isFinite(media.duration)
              ? media.duration
              : Number.POSITIVE_INFINITY;
            media.currentTime = Math.max(
              0,
              Math.min(max, media.currentTime + step * 2),
            );
          }
          break;

        case 'ArrowUp': {
          const next = clampVolume(
            (media.muted ? 0 : media.volume) + volumeStep,
          );
          if (onVolumeChange) onVolumeChange(next);
          else media.volume = next;
          break;
        }

        case 'ArrowDown': {
          const next = clampVolume(
            (media.muted ? 0 : media.volume) - volumeStep,
          );
          if (onVolumeChange) onVolumeChange(next);
          else media.volume = next;
          break;
        }

        case 'm':
        case 'M':
          if (onToggleMute) onToggleMute();
          else media.muted = !media.muted;
          break;

        case 'Home':
          if (onSeekTo) onSeekTo(0);
          else media.currentTime = 0;
          break;

        case 'End':
          if (Number.isFinite(media.duration)) {
            if (onSeekTo) onSeekTo(media.duration);
            else media.currentTime = media.duration;
          }
          break;

        case 'f':
        case 'F':
          if (media instanceof HTMLVideoElement && onToggleFullscreen) {
            onToggleFullscreen();
          } else {
            handled = false;
          }
          break;

        default:
          handled = false;
      }

      if (handled) {
        event.preventDefault();
      }
    };

    container.addEventListener('keydown', handleKeyDown as EventListener);
    return () => {
      container.removeEventListener('keydown', handleKeyDown as EventListener);
    };
  }, [
    containerRef,
    mediaRef,
    enabled,
    seekStep,
    volumeStep,
    onTogglePlay,
    onSkip,
    onSeekTo,
    onVolumeChange,
    onToggleMute,
    onToggleFullscreen,
  ]);
}
