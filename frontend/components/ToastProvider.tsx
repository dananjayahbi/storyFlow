'use client';

import { Toaster } from '@/components/ui/sonner';

/**
 * Global toast notification provider.
 *
 * Renders the Sonner `Toaster` with the project-standard configuration:
 *  - position: bottom-right (avoids sidebar and main content overlap)
 *  - richColors: automatic green/red/yellow/blue per toast type
 *  - closeButton: manual dismiss affordance
 *  - duration: 4 000 ms auto-dismiss
 *
 * Mount once in `app/layout.tsx`.
 *
 * Usage patterns:
 *   toast.success("Settings saved successfully")   — after successful user action
 *   toast.error("Failed to upload image: …")       — when a user action fails
 *   toast.warning("Voice changed. Re-generate …")  — non-blocking warning
 *   toast.info("Rendering video…")                  — status update for long ops
 */
export function ToastProvider() {
  return (
    <Toaster
      position="bottom-right"
      richColors
      closeButton
      duration={4000}
    />
  );
}
