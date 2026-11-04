'use client';

import { useRef } from 'react';
import { Camera, Film, Loader2, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Project } from '@/lib/types';
import { cn } from '@/lib/utils';

interface ProjectThumbnailProps {
  project: Project;
  className?: string;
  /** Show upload/remove controls over the image. */
  editable?: boolean;
  /** Disable the controls while an upload/removal is in flight. */
  busy?: boolean;
  onUpload?: (file: File) => void;
  onRemove?: () => void;
  /** Hide the "No preview yet" caption (used by compact table rows). */
  compact?: boolean;
}

/**
 * Cover image for a project row/tile.
 *
 * Priority is handled by the API: a manually uploaded thumbnail wins, then the
 * first segment image.  When neither exists we show an animated placeholder so
 * the grid still feels alive instead of rendering an empty grey box.
 */
export function ProjectThumbnail({
  project,
  className,
  editable = false,
  busy = false,
  onUpload,
  onRemove,
  compact = false,
}: ProjectThumbnailProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hasImage = Boolean(project.thumbnail_url);

  return (
    <div
      className={cn(
        'group/thumb relative overflow-hidden bg-muted',
        className,
      )}
    >
      {hasImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={project.thumbnail_url ?? ''}
          alt={`${project.title} thumbnail`}
          loading="lazy"
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
        />
      ) : (
        <div
          role="img"
          aria-label={`${project.title} has no thumbnail yet`}
          className="project-thumb-placeholder flex h-full w-full flex-col items-center justify-center gap-1 text-white/80"
        >
          <span className="project-thumb-placeholder-glow pointer-events-none absolute inset-0 m-auto size-24 rounded-full bg-white/20 blur-2xl" />
          <Film
            className={cn(
              'project-thumb-placeholder-icon relative drop-shadow',
              compact ? 'size-4' : 'size-7',
            )}
          />
          {!compact && (
            <span className="relative text-[10px] font-medium uppercase tracking-wide">
              No preview yet
            </span>
          )}
        </div>
      )}

      {editable && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="sr-only"
            aria-label={`Upload thumbnail for ${project.title}`}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload?.(file);
              event.target.value = '';
            }}
          />
          <div
            className={cn(
              'absolute inset-0 flex items-end justify-end gap-1 bg-gradient-to-t from-black/60 via-transparent to-transparent p-1.5 transition-opacity',
              'opacity-0 group-hover/thumb:opacity-100 focus-within:opacity-100',
              compact && 'p-1',
            )}
            onClick={(event) => event.stopPropagation()}
          >
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="secondary"
                  className="size-7 bg-background/90 hover:bg-background"
                  disabled={busy}
                  onClick={(event) => {
                    event.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  aria-label={`Upload thumbnail for ${project.title}`}
                >
                  <Camera className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {project.has_manual_thumbnail
                  ? 'Replace manual thumbnail'
                  : 'Use a manual thumbnail'}
              </TooltipContent>
            </Tooltip>

            {project.has_manual_thumbnail && onRemove && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="secondary"
                    className="size-7 bg-background/90 text-destructive hover:bg-background"
                    disabled={busy}
                    onClick={(event) => {
                      event.stopPropagation();
                      onRemove();
                    }}
                    aria-label={`Remove manual thumbnail for ${project.title}`}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Remove manual thumbnail</TooltipContent>
              </Tooltip>
            )}
          </div>
          {busy && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/45">
              <Loader2 className="size-4 animate-spin text-white" />
            </div>
          )}
        </>
      )}
    </div>
  );
}
