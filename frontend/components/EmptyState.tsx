'use client';

import type { LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

// ── Props ──────────────────────────────────────────────────────────
interface EmptyStateProps {
  /** Lucide icon component rendered large and muted above the title. */
  icon: LucideIcon;
  /** Heading text (e.g. "No projects yet"). */
  title: string;
  /** Explanatory body text in muted color. */
  description: string;
  /** Optional CTA button label. */
  actionLabel?: string;
  /** Optional CTA click handler. */
  onAction?: () => void;
}

// ── Component ──────────────────────────────────────────────────────

/**
 * Reusable empty-state placeholder displayed when lists or
 * sections have no content. Shows an icon, title, description,
 * and an optional call-to-action button.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Icon className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-semibold mb-1">{title}</h3>
      <p className="text-muted-foreground max-w-xs mb-4">{description}</p>
      {actionLabel && onAction && (
        <Button onClick={onAction}>{actionLabel}</Button>
      )}
    </div>
  );
}
