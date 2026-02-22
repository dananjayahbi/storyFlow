'use client';

import type { Segment, UpdateSegmentPayload } from '@/lib/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { SegmentCard } from './SegmentCard';
import { EmptyState } from '@/components/EmptyState';
import { FileText, Plus } from 'lucide-react';

interface TimelineProps {
  segments: Segment[];
  onAddSegment?: () => Promise<void>;
  onUpdateSegment: (id: string, data: UpdateSegmentPayload) => Promise<void>;
  onDeleteSegment: (id: string) => Promise<void>;
  onUploadImage: (id: string, file: File) => Promise<void>;
  onRemoveImage: (id: string) => Promise<void>;
}

export function Timeline({
  segments, onAddSegment, onUpdateSegment, onDeleteSegment, onUploadImage, onRemoveImage,
}: TimelineProps) {
  if (segments.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="No segments"
        description="Add a segment or import a story from the dashboard."
        actionLabel="+ Add Segment"
        onAction={onAddSegment}
      />
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
        {/* Add segment button at the bottom of the list */}
        {onAddSegment && (
          <Button
            variant="outline"
            className="w-full border-dashed"
            onClick={onAddSegment}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Segment
          </Button>
        )}
      </div>
    </ScrollArea>
  );
}
