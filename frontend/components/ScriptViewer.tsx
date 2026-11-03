'use client';

import { Image as ImageIcon, Mic2, RotateCcw } from 'lucide-react';
import type { ScriptContent } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface ScriptViewerProps {
  script: ScriptContent;
  className?: string;
  /** Highlight/allow selection of one segment (used by Script Craft). */
  selectable?: boolean;
  selectedIndex?: number | null;
  onSelectSegment?: (index: number) => void;
  onRewriteSegment?: (index: number) => void;
}

/** Human-friendly rendering of a generated StoryFlow script. */
export function ScriptViewer({
  script,
  className,
  selectable = false,
  selectedIndex = null,
  onSelectSegment,
  onRewriteSegment,
}: ScriptViewerProps) {
  const segments = Array.isArray(script?.segments) ? script.segments : [];

  return (
    <div className={className}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold tracking-tight">
            {script?.title || 'Untitled script'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {segments.length} narration segment{segments.length === 1 ? '' : 's'}
            {selectable ? ' · click a block to select it' : ''}
          </p>
        </div>
        <Badge variant="secondary" className="shrink-0">
          {segments.length} segments
        </Badge>
      </div>

      <div className="space-y-3">
        {segments.map((segment, index) => {
          const selected = selectedIndex === index;
          return (
            <Card
              key={index}
              role={selectable ? 'button' : undefined}
              tabIndex={selectable ? 0 : undefined}
              aria-pressed={selectable ? selected : undefined}
              onClick={
                selectable && onSelectSegment
                  ? () => onSelectSegment(index)
                  : undefined
              }
              onKeyDown={
                selectable && onSelectSegment
                  ? (event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onSelectSegment(index);
                      }
                    }
                  : undefined
              }
              className={cn(
                'overflow-hidden transition',
                selectable && 'cursor-pointer hover:border-primary/50',
                selected && 'ring-2 ring-primary ring-offset-2 ring-offset-background'
              )}
            >
              <CardHeader className="flex flex-row items-center gap-3 space-y-0 border-b bg-muted/30 py-3">
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                    selected
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-primary/10 text-primary'
                  )}
                >
                  {index + 1}
                </span>
                <CardTitle className="flex-1 text-sm font-medium text-muted-foreground">
                  Segment {index + 1}
                  {selected && (
                    <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider text-primary">
                      selected
                    </span>
                  )}
                </CardTitle>
                {onRewriteSegment && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectSegment?.(index);
                      onRewriteSegment(index);
                    }}
                  >
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                    Rewrite
                  </Button>
                )}
              </CardHeader>
              <CardContent className="space-y-3 pt-4">
                <div className="flex gap-2.5">
                  <Mic2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <p className="text-sm leading-relaxed whitespace-pre-line">
                    {segment.text_content}
                  </p>
                </div>
                {segment.image_prompt && (
                  <div className="flex gap-2.5 rounded-md border border-dashed bg-muted/30 p-3">
                    <ImageIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Image prompt
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {segment.image_prompt}
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
