'use client';

import { Image as ImageIcon, Mic2 } from 'lucide-react';
import type { ScriptContent } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface ScriptViewerProps {
  script: ScriptContent;
  className?: string;
}

/** Human-friendly rendering of a generated StoryFlow script. */
export function ScriptViewer({ script, className }: ScriptViewerProps) {
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
          </p>
        </div>
        <Badge variant="secondary" className="shrink-0">
          {segments.length} segments
        </Badge>
      </div>

      <div className="space-y-3">
        {segments.map((segment, index) => (
          <Card key={index} className="overflow-hidden">
            <CardHeader className="flex flex-row items-center gap-3 space-y-0 border-b bg-muted/30 py-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                {index + 1}
              </span>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Segment {index + 1}
              </CardTitle>
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
        ))}
      </div>
    </div>
  );
}
