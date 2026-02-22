'use client';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface KeyboardShortcutsHelpProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ShortcutRow {
  keys: string[];
  description: string;
}

const SHORTCUT_LIST: ShortcutRow[] = [
  { keys: ['Ctrl', 'Enter'], description: 'Generate audio for the current segment' },
  { keys: ['Ctrl', 'Shift', 'Enter'], description: 'Export / render the full video' },
  { keys: ['Ctrl', 'S'], description: 'Save global settings (when panel is open)' },
  { keys: ['Esc'], description: 'Close any open modal or panel' },
  { keys: ['?'], description: 'Open this keyboard shortcuts help' },
];

function KeyBadge({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[1.5rem] h-6 px-1.5 rounded border border-border bg-muted text-xs font-mono font-medium text-foreground shadow-sm">
      {children}
    </kbd>
  );
}

export function KeyboardShortcutsHelp({ open, onOpenChange }: KeyboardShortcutsHelpProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {SHORTCUT_LIST.map((row, i) => (
            <div key={i} className="flex items-center justify-between gap-4">
              <span className="text-sm text-muted-foreground">{row.description}</span>
              <div className="flex items-center gap-1 shrink-0">
                {row.keys.map((k, j) => (
                  <span key={j} className="flex items-center gap-1">
                    {j > 0 && <span className="text-muted-foreground text-xs">+</span>}
                    <KeyBadge>{k}</KeyBadge>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-muted-foreground mt-2">
          Shortcuts are disabled while typing in text fields (except Esc).
        </p>
      </DialogContent>
    </Dialog>
  );
}
