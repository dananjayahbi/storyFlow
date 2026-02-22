'use client';

import React, { useCallback, useState } from 'react';
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
import { Lock, LockOpen, Trash2, MoreVertical, RefreshCw, AlertTriangle, ChevronDown, ChevronUp, Captions } from 'lucide-react';
import { SegmentTextEditor } from './SegmentTextEditor';
import { ImageUploader } from './ImageUploader';
import { ImagePromptDisplay } from './ImagePromptDisplay';
import { AudioPlayer } from './AudioPlayer';
import { GenerateAudioButton } from './GenerateAudioButton';
import { AudioStatusBadge } from './AudioStatusBadge';

/** Stable reference for the default (idle) audio status — avoids new object on each render. */
const DEFAULT_AUDIO_STATUS: AudioGenerationState = { status: 'idle' };

/** Approximate character count threshold for showing "Show more" toggle. */
const TEXT_TRUNCATION_THRESHOLD = 150;

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
  const isFailed = generationStatus.status === 'failed';

  // Local UI state
  const [isTextExpanded, setIsTextExpanded] = useState(false);
  const [isSubtitlePreviewOpen, setIsSubtitlePreviewOpen] = useState(false);

  const isLongText = segment.text_content.length > TEXT_TRUNCATION_THRESHOLD;

  // Stable callback refs — prevent unnecessary child re-renders
  const handleLockToggle = useCallback(() => {
    onUpdate(segment.id, { is_locked: !segment.is_locked });
  }, [onUpdate, segment.id, segment.is_locked]);

  const handleGenerateAudio = useCallback(() => {
    generateAudio(segment.id);
  }, [generateAudio, segment.id]);

  // Split text_content into word chunks for subtitle preview
  const subtitleChunks = segment.text_content
    ? segment.text_content.split(/\s+/).filter(Boolean)
    : [];

  // Determine border color class based on state
  const borderClass = isFailed
    ? 'border-destructive/50'
    : isGenerating
      ? 'border-amber-400'
      : segment.is_locked
        ? 'border-amber-300'
        : '';

  return (
    <Card className={`p-4 space-y-3 transition-all duration-200 ease-in-out hover:shadow-md ${
      borderClass
    } ${isGenerating ? 'animate-pulse' : ''}`}>
      {/* Header Row */}
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
              <Button variant="ghost" size="icon" onClick={handleLockToggle} disabled={isGenerating}>
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
              <Button variant="ghost" size="icon" className="text-destructive" disabled={isGenerating}>
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

      {/* Text Content Area with truncation */}
      <div>
        <div className={isLongText && !isTextExpanded ? 'max-h-[4.5rem] overflow-hidden' : ''}>
          <SegmentTextEditor
            segmentId={segment.id}
            initialContent={segment.text_content}
            isLocked={segment.is_locked || isGenerating}
            onSave={onUpdate}
          />
        </div>
        {isLongText && (
          <button
            className="mt-1 text-xs text-muted-foreground hover:text-foreground transition-colors duration-200"
            onClick={() => setIsTextExpanded(!isTextExpanded)}
          >
            {isTextExpanded ? (
              <span className="flex items-center gap-1"><ChevronUp className="h-3 w-3" /> Show less</span>
            ) : (
              <span className="flex items-center gap-1"><ChevronDown className="h-3 w-3" /> Show more</span>
            )}
          </button>
        )}
      </div>

      {/* Inline Error Display */}
      {isFailed && (
        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 px-3 py-2 rounded transition-all duration-200">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">
            {generationStatus.status === 'failed' ? generationStatus.error : 'An error occurred'}
          </span>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={handleGenerateAudio}
            disabled={segment.is_locked}
          >
            Retry
          </Button>
        </div>
      )}

      <Separator />

      {/* Image + Prompt Row */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="md:w-2/5">
          <ImageUploader
            segmentId={segment.id}
            currentImage={segment.image_file}
            isLocked={segment.is_locked || isGenerating}
            onUpload={onUploadImage}
            onRemove={onRemoveImage}
          />
        </div>
        <div className="md:w-3/5">
          <ImagePromptDisplay prompt={segment.image_prompt} />
        </div>
      </div>

      {/* Subtitle Preview Toggle */}
      <div>
        <button
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors duration-200"
          onClick={() => setIsSubtitlePreviewOpen(!isSubtitlePreviewOpen)}
        >
          <Captions className="h-3 w-3" />
          <span>Subtitle Preview</span>
          {isSubtitlePreviewOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
        <div
          className={`overflow-hidden transition-all duration-200 ease-in-out ${
            isSubtitlePreviewOpen ? 'max-h-40 mt-2' : 'max-h-0'
          }`}
        >
          {subtitleChunks.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {subtitleChunks.map((word, i) => (
                <span
                  key={i}
                  className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs font-mono"
                >
                  {word}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">No subtitles generated</p>
          )}
        </div>
      </div>

      {/* Audio Section */}
      <div className="overflow-hidden">
      {segment.audio_file && !isGenerating ? (
        <div className="space-y-2">
          <AudioPlayer
            audioUrl={segment.audio_file}
            duration={segment.audio_duration ?? 0}
          />
          {isStale && (
            <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-3 py-1.5 rounded transition-all duration-200">
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
