'use client';

import { useState, useMemo } from 'react';
import { useKeyboardShortcuts, ShortcutDefinition } from '@/hooks/useKeyboardShortcuts';
import { KeyboardShortcutsHelp } from '@/components/KeyboardShortcutsHelp';
import { useProjectStore } from '@/lib/stores';
import { toast } from 'sonner';

/**
 * KeyboardShortcutProvider — a client component mounted in layout.tsx
 * that wires up the global keyboard shortcuts hook and renders the
 * keyboard shortcuts help dialog.
 */
export function KeyboardShortcutProvider() {
  const [helpOpen, setHelpOpen] = useState(false);

  // Pull store actions (only subscribe to what we need)
  const generateAllAudio = useProjectStore((s) => s.generateAllAudio);
  const startRender = useProjectStore((s) => s.startRender);
  const project = useProjectStore((s) => s.project);
  const segments = useProjectStore((s) => s.segments);
  const renderStatus = useProjectStore((s) => s.renderStatus);

  const shortcuts = useMemo<ShortcutDefinition[]>(
    () => [
      // ── Ctrl+Enter — Generate All Audio ──
      {
        key: 'Enter',
        ctrl: true,
        label: 'Ctrl+Enter',
        description: 'Generate audio for segments',
        action: () => {
          if (!project) {
            toast.info('Open a project first to generate audio.');
            return;
          }
          if (segments.length === 0) {
            toast.info('No segments to generate audio for.');
            return;
          }
          generateAllAudio();
          toast.info('Audio generation started.');
        },
      },

      // ── Ctrl+Shift+Enter — Render / Export Video ──
      {
        key: 'Enter',
        ctrl: true,
        shift: true,
        label: 'Ctrl+Shift+Enter',
        description: 'Export / render video',
        action: () => {
          if (!project) {
            toast.info('Open a project first to render video.');
            return;
          }
          const hasAudio = segments.some((s) => s.audio_file);
          if (!hasAudio) {
            toast.info('Generate audio for at least one segment before rendering.');
            return;
          }
          if (renderStatus === 'rendering') {
            toast.info('A render is already in progress.');
            return;
          }
          startRender();
          toast.info('Video render started.');
        },
      },

      // ── Ctrl+S — Save Settings ──
      {
        key: 'KeyS',
        ctrl: true,
        label: 'Ctrl+S',
        description: 'Save global settings',
        action: () => {
          // Try to find and click the settings save button
          const saveBtn = document.querySelector<HTMLButtonElement>(
            '[data-settings-save]',
          );
          if (saveBtn) {
            saveBtn.click();
          } else {
            toast.info('Open the Settings panel to save changes.');
          }
        },
      },

      // ── Escape — Close modal / panel ──
      {
        key: 'Escape',
        label: 'Esc',
        description: 'Close modal or panel',
        allowInInput: true,
        action: () => {
          // Radix dialogs already handle Escape natively.
          // We handle any custom panels (e.g. settings accordion).
          const settingsToggle = document.querySelector<HTMLButtonElement>(
            '[data-settings-close]',
          );
          if (settingsToggle) {
            settingsToggle.click();
          }
          // Blur the currently focused element so user exits input fields
          if (document.activeElement instanceof HTMLElement) {
            document.activeElement.blur();
          }
        },
      },

      // ── ? — Help dialog ──
      {
        key: '?',
        label: '?',
        description: 'Show keyboard shortcuts',
        action: () => {
          setHelpOpen(true);
        },
      },
    ],
    [project, segments, generateAllAudio, startRender, renderStatus],
  );

  useKeyboardShortcuts(shortcuts);

  return <KeyboardShortcutsHelp open={helpOpen} onOpenChange={setHelpOpen} />;
}
