'use client';

import React, { useCallback } from 'react';
import type { Segment, UpdateSegmentPayload, AudioGenerationState } from '@/lib/types';
import { useProjectStore } from '@/lib/stores';
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
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Lock, LockOpen, Trash2, MoreVertical, RefreshCw, AlertTriangle } from 'lucide-react';
import { SegmentTextEditor } from './SegmentTextEditor';
import { ImageUploader } from './ImageUploader';
import { ImagePromptDisplay } from './ImagePromptDisplay';
import { AudioPlayer } from './AudioPlayer';
import { GenerateAudioButton } from './GenerateAudioButton';
import { AudioStatusBadge } from './AudioStatusBadge';

/** Stable reference for the default (idle) audio status — avoids new object on each render. */
const DEFAULT_AUDIO_STATUS: AudioGenerationState = { status: 'idle' };

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
  // Granular selector: only re-renders when THIS segment's audio status changes,
  // not when other segments' statuses update in the audioGenerationStatus map.
  const generationStatus = useProjectStore(
    (state) => state.audioGenerationStatus[segment.id] ?? DEFAULT_AUDIO_STATUS,
  );
  const generateAudio = useProjectStore((state) => state.generateAudio);
  const isStale = useProjectStore(
    (state) => state.staleAudioSegments.has(segment.id),
  );

  const isGenerating = generationStatus.status === 'generating';

  // Stable callback refs — prevent unnecessary child re-renders
  const handleLockToggle = useCallback(() => {
    onUpdate(segment.id, { is_locked: !segment.is_locked });
  }, [onUpdate, segment.id, segment.is_locked]);

  const handleGenerateAudio = useCallback(() => {
    generateAudio(segment.id);
  }, [generateAudio, segment.id]);

  return (
    <Card className={`p-4 space-y-3 ${
      segment.is_locked ? 'border-amber-300' : ''
    } ${isGenerating ? 'animate-pulse border-amber-400' : ''}`}>
      {/* 3a. Header Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            #{segment.sequence_index + 1}
          </Badge>
          <AudioStatusBadge
            audioFile={segment.audio_file}
            audioDuration={segment.audio_duration}
            generationStatus={generationStatus}
          />
        </div>
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
          {/* More actions dropdown */}
          {segment.audio_file && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={segment.is_locked || isGenerating}
                  onClick={handleGenerateAudio}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Regenerate Audio
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
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

      {/* 3e. Audio Section */}
      <div className="overflow-hidden">
      {segment.audio_file && !isGenerating ? (
        <div className="space-y-2">
          <AudioPlayer
            audioUrl={segment.audio_file}
            duration={segment.audio_duration ?? 0}
          />
          {isStale && (
            <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-3 py-1.5 rounded">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>Text changed — audio may be out of sync.</span>
              <button
                className="ml-auto underline hover:no-underline font-medium"
                onClick={handleGenerateAudio}
              >
                Regenerate
              </button>
            </div>
          )}
        </div>
      ) : (
        <GenerateAudioButton
          segmentId={segment.id}
          isLocked={segment.is_locked}
          generationStatus={generationStatus}
          onGenerate={handleGenerateAudio}
        />
      )}
      </div>
    </Card>
  );
}

export const SegmentCard = React.memo(SegmentCardComponent);
