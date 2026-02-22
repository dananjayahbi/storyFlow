'use client';

import { useEffect, useCallback } from 'react';

// ── Types ──

export interface ShortcutDefinition {
  /** Primary key code (e.g. 'KeyS', 'Enter', 'Escape') */
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  /** Human-readable label for the help dialog */
  label: string;
  /** Description of what the shortcut does */
  description: string;
  /** Callback to invoke when the shortcut is triggered */
  action: () => void;
  /**
   * If true, shortcut fires even when the user is typing in an
   * input/textarea/select/contenteditable field. Defaults to false.
   */
  allowInInput?: boolean;
}

// ── Helpers ──

function isInputElement(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if ((el as HTMLElement).isContentEditable) return true;
  return false;
}

// ── Hook ──

/**
 * useKeyboardShortcuts — registers a single global `keydown` listener
 * that matches incoming events against a list of shortcut definitions.
 *
 * When typing in form fields, all shortcuts are suppressed except those
 * with `allowInInput: true` (typically Escape).
 */
export function useKeyboardShortcuts(shortcuts: ShortcutDefinition[]) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const inInput = isInputElement(document.activeElement);

      for (const shortcut of shortcuts) {
        // Match modifier keys
        const ctrlMatch = !!shortcut.ctrl === (e.ctrlKey || e.metaKey);
        const shiftMatch = !!shortcut.shift === e.shiftKey;
        const altMatch = !!shortcut.alt === e.altKey;

        // Match primary key
        const keyMatch = e.code === shortcut.key || e.key === shortcut.key;

        if (ctrlMatch && shiftMatch && altMatch && keyMatch) {
          // Skip if user is in an input and shortcut doesn't allow it
          if (inInput && !shortcut.allowInInput) continue;

          e.preventDefault();
          e.stopPropagation();
          shortcut.action();
          return;
        }
      }
    },
    [shortcuts],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);
}
