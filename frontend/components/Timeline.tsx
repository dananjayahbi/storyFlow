'use client';

import type { Segment, UpdateSegmentPayload } from '@/lib/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import { SegmentCard } from './SegmentCard';

interface TimelineProps {
  segments: Segment[];
  onUpdateSegment: (id: string, data: UpdateSegmentPayload) => Promise<void>;
  onDeleteSegment: (id: string) => Promise<void>;
  onUploadImage: (id: string, file: File) => Promise<void>;
  onRemoveImage: (id: string) => Promise<void>;
}

export function Timeline({
  segments, onUpdateSegment, onDeleteSegment, onUploadImage, onRemoveImage,
}: TimelineProps) {
  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-lg text-muted-foreground">No segments yet.</p>
        <p className="text-sm text-muted-foreground">
          Import a story to get started.
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[calc(100vh-280px)] lg:h-[calc(100vh-200px)]">
      <div className="space-y-4 p-4">
        {segments.map((segment) => (
          <SegmentCard
            key={segment.id}
            segment={segment}
            onUpdate={onUpdateSegment}
            onDelete={onDeleteSegment}
            onUploadImage={onUploadImage}
            onRemoveImage={onRemoveImage}
          />
        ))}
      </div>
    </ScrollArea>
  );
}
