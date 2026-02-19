'use client';

import React from 'react';
import type { Segment, UpdateSegmentPayload } from '@/lib/types';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Lock, LockOpen, Trash2 } from 'lucide-react';
import { SegmentTextEditor } from './SegmentTextEditor';
import { ImageUploader } from './ImageUploader';
import { ImagePromptDisplay } from './ImagePromptDisplay';

interface SegmentCardProps {
  segment: Segment;
  onUpdate: (id: string, data: UpdateSegmentPayload) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onUploadImage: (id: string, file: File) => Promise<void>;
  onRemoveImage: (id: string) => Promise<void>;
}

function SegmentCardComponent({
  segment, onUpdate, onDelete, onUploadImage, onRemoveImage,
}: SegmentCardProps) {
  const handleLockToggle = () => {
    onUpdate(segment.id, { is_locked: !segment.is_locked });
  };

  return (
    <Card className={`p-4 space-y-3 ${
      segment.is_locked ? 'border-amber-300' : ''
    }`}>
      {/* 3a. Header Row */}
      <div className="flex items-center justify-between">
        <Badge variant="secondary">
          #{segment.sequence_index + 1}
        </Badge>
        <div className="flex items-center gap-1">
          {/* Lock toggle */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={handleLockToggle}>
                {segment.is_locked ? (
                  <Lock className="h-4 w-4" />
                ) : (
                  <LockOpen className="h-4 w-4 text-muted-foreground" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {segment.is_locked ? 'Unlock segment' : 'Lock segment'}
            </TooltipContent>
          </Tooltip>
          {/* Delete button with confirmation */}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="icon" className="text-destructive">
                <Trash2 className="h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Segment</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete Segment #{segment.sequence_index + 1}?
                  This action cannot be undone. Any uploaded images will also be removed.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => onDelete(segment.id)}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* 3b. Text Content Area */}
      <SegmentTextEditor
        segmentId={segment.id}
        initialContent={segment.text_content}
        isLocked={segment.is_locked}
        onSave={onUpdate}
      />

      <Separator />

      {/* 3c. Image + Prompt Row */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="md:w-2/5">
          <ImageUploader
            segmentId={segment.id}
            currentImage={segment.image_file}
            isLocked={segment.is_locked}
            onUpload={onUploadImage}
            onRemove={onRemoveImage}
          />
        </div>
        <div className="md:w-3/5">
          <ImagePromptDisplay prompt={segment.image_prompt} />
        </div>
      </div>

      {/* 3e. Audio Placeholder */}
      <div className="rounded-md bg-muted/50 p-3 opacity-60">
        <p className="text-sm text-muted-foreground">
          🔊 Audio — Coming in Phase 03
        </p>
      </div>
    </Card>
  );
}

export const SegmentCard = React.memo(SegmentCardComponent);
