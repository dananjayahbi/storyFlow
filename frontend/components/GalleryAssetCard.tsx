'use client';

import { useEffect, useRef, useState } from 'react';
import { Download, Play, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { GalleryItem, RenderingStatus } from '@/lib/types';
import {
  GALLERY_STATUS_OPTIONS,
  formatGalleryFileSize,
  formatGalleryRelativeTime,
  galleryStatusMeta,
} from '@/lib/gallery';
import { getStreamUrl } from '@/lib/api';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

/**
 * Long video titles scroll like a news ticker on hover.  The text only
 * animates when it actually overflows its one-line tile header, and the
 * duration scales with the hidden distance so long titles stay readable.
 */
function MarqueeTitle({ text }: { text: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLSpanElement>(null);
  const [overflow, setOverflow] = useState(0);

  useEffect(() => {
    const measure = () => {
      const container = containerRef.current;
      const track = trackRef.current;
      if (!container || !track) return;
      setOverflow(Math.max(0, track.scrollWidth - container.clientWidth));
    };

    measure();
    const observer =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(measure)
        : null;
    if (containerRef.current) observer?.observe(containerRef.current);
    if (trackRef.current) observer?.observe(trackRef.current);
    return () => observer?.disconnect();
  }, [text]);

  return (
    <div ref={containerRef} className="min-w-0 overflow-hidden">
      <span
        ref={trackRef}
        className={cn(
          'gallery-title-track block whitespace-nowrap',
          overflow > 0 && 'gallery-title-overflow',
        )}
        style={
          overflow > 0
            ? ({
                '--marquee-distance': `-${overflow}px`,
                '--marquee-duration': `${Math.max(5, overflow / 45)}s`,
              } as React.CSSProperties)
            : undefined
        }
      >
        {text}
      </span>
    </div>
  );
}

interface GalleryAssetCardProps {
  item: GalleryItem;
  selected?: boolean;
  onSelectedChange?: (selected: boolean) => void;
  onOpen?: () => void;
  onDownload?: (event: React.MouseEvent) => void;
  onDelete?: (event: React.MouseEvent) => void;
  /** When provided, the status badge becomes a quick status changer. */
  onStatusChange?: (status: RenderingStatus) => void;
  /** Show which project produced this asset (main Gallery only). */
  showProject?: boolean;
}

export function GalleryAssetCard({
  item,
  selected = false,
  onSelectedChange,
  onOpen,
  onDownload,
  onDelete,
  onStatusChange,
  showProject = true,
}: GalleryAssetCardProps) {
  const status = galleryStatusMeta(item.status);

  return (
    <Card
      className={cn(
        'gallery-title-hover group overflow-hidden cursor-pointer break-inside-avoid mb-3 transition-all hover:ring-2 hover:ring-primary/30',
        selected && 'ring-2 ring-primary',
      )}
      onClick={onOpen}
    >
      <div
        className="relative bg-black"
        style={{
          aspectRatio: `${item.resolution_width} / ${item.resolution_height}`,
        }}
      >
        <video
          src={getStreamUrl(item.id)}
          className="h-full w-full object-contain"
          preload="metadata"
          muted
          playsInline
          onMouseEnter={(event) => {
            const video = event.currentTarget;
            video.currentTime = 0;
            video.play().catch(() => {});
          }}
          onMouseLeave={(event) => {
            const video = event.currentTarget;
            video.pause();
            video.currentTime = 0;
          }}
        />

        {/* Play affordance */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity group-hover:opacity-100">
          <div className="rounded-full bg-white/90 p-3 dark:bg-black/70">
            <Play className="size-6 text-foreground" />
          </div>
        </div>

        {/* Multi-select */}
        {onSelectedChange && (
          <div
            className={cn(
              'absolute left-2 top-2 rounded-md bg-black/55 p-1.5 transition-opacity',
              selected
                ? 'opacity-100'
                : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100',
            )}
            onClick={(event) => event.stopPropagation()}
          >
            <Checkbox
              checked={selected}
              onCheckedChange={(checked) => onSelectedChange(checked === true)}
              aria-label={`Select ${item.title}`}
              className="border-white/70 data-[state=checked]:border-primary data-[state=checked]:bg-primary"
            />
          </div>
        )}

        {/* Status */}
        <div className="absolute bottom-2 left-2">
          {onStatusChange ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  title="Change publishing status"
                  className="cursor-pointer rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={(event) => event.stopPropagation()}
                >
                  <Badge
                    variant="outline"
                    className={cn(
                      'gap-1 text-[10px] backdrop-blur',
                      status.badge,
                    )}
                  >
                    <span className={cn('size-1.5 rounded-full', status.dot)} />
                    {status.label}
                  </Badge>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                onClick={(event) => event.stopPropagation()}
              >
                {GALLERY_STATUS_OPTIONS.map((option) => (
                  <DropdownMenuItem
                    key={option.value}
                    disabled={option.value === item.status}
                    onClick={() => onStatusChange(option.value)}
                  >
                    <span
                      className={cn(
                        'mr-2 size-2 rounded-full',
                        galleryStatusMeta(option.value).dot,
                      )}
                    />
                    {option.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Badge
              variant="outline"
              className={cn('gap-1 text-[10px] backdrop-blur', status.badge)}
            >
              <span className={cn('size-1.5 rounded-full', status.dot)} />
              {status.label}
            </Badge>
          )}
        </div>

        {/* Resolution */}
        <div className="absolute right-2 top-2">
          <Badge
            variant="outline"
            className="border-white/20 bg-black/60 text-xs text-white"
          >
            {item.resolution_width}×{item.resolution_height}
          </Badge>
        </div>
      </div>

      <CardContent className="pt-2.5 pb-3">
        <div className="flex items-start justify-between gap-1.5">
          <div className="min-w-0 flex-1">
            <MarqueeTitle text={item.title} />
            {showProject && item.project_title !== item.title && (
              <p className="mt-0.5 truncate text-[11px] text-muted-foreground/80">
                {item.project_title}
              </p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
              <span>{formatGalleryRelativeTime(item.created_at)}</span>
              <span>{item.segment_count} segments</span>
              <span>{formatGalleryFileSize(item.file_size)}</span>
            </div>
          </div>
          <div className="flex shrink-0 items-center">
            {onDownload && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDownload(event);
                    }}
                  >
                    <Download className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Download</TooltipContent>
              </Tooltip>
            )}
            {onDelete && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8 text-muted-foreground hover:text-destructive"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDelete(event);
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete rendering</TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
