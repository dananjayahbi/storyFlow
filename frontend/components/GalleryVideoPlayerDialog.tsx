'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  getDownloadUrl,
  getStreamUrl,
  updateGalleryItemStatus,
} from '@/lib/api';
import { GalleryItem, RenderingStatus } from '@/lib/types';
import {
  GALLERY_STATUS_OPTIONS,
  formatGalleryFileSize,
  galleryStatusMeta,
} from '@/lib/gallery';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Download,
  ExternalLink,
  Maximize2,
  Pause,
  PictureInPicture2,
  Play,
  Repeat,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { cn, formatGenerationTime } from '@/lib/utils';
import { useMediaKeyboardShortcuts } from '@/lib/useMediaKeyboardShortcuts';

function formatAbsoluteDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

interface GalleryVideoPlayerDialogProps {
  /** The asset to play. Pass `null` to close the dialog. */
  item: GalleryItem | null;
  onClose: () => void;
  /**
   * Notified after a status change so the caller can refresh its list.
   * The passed item already contains the new status.
   */
  onItemUpdated?: (item: GalleryItem) => void;
  /** Optional link to the owning project, shown in the player header. */
  projectHref?: string;
}

/**
 * Full-featured player for one rendered gallery asset.  It is shared by the
 * main Gallery page and the Project gallery modal so that clicking a tile in
 * either place opens the same popup player with per-asset status controls.
 */
export function GalleryVideoPlayerDialog({
  item,
  onClose,
  onItemUpdated,
  projectHref,
}: GalleryVideoPlayerDialogProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  const resetPlayer = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      video.pause();
      video.src = '';
    }
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setPlaybackRate(1);
  }, []);

  // Release the video element whenever the player closes or swaps assets.
  useEffect(() => {
    if (!item) resetPlayer();
  }, [item, resetPlayer]);

  const handleClose = useCallback(() => {
    resetPlayer();
    onClose();
  }, [onClose, resetPlayer]);

  const handleDownload = useCallback(() => {
    if (!item) return;
    const anchor = document.createElement('a');
    anchor.href = getDownloadUrl(item.id);
    anchor.download = `${item.title}.mp4`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  }, [item]);

  const handleStatusChange = useCallback(
    async (status: RenderingStatus) => {
      if (!item || status === item.status) return;
      setIsUpdatingStatus(true);
      try {
        await updateGalleryItemStatus(item.id, status);
        const updated: GalleryItem = {
          ...item,
          status,
          status_label: galleryStatusMeta(status).label,
          published_at:
            status === 'published' ? new Date().toISOString() : null,
        };
        onItemUpdated?.(updated);
        toast.success(
          `Marked "${item.title}" ${galleryStatusMeta(status).label.toLowerCase()}`,
        );
      } catch {
        toast.error('Could not update this rendering\u2019s status.');
      } finally {
        setIsUpdatingStatus(false);
      }
    },
    [item, onItemUpdated],
  );

  // ── Player controls ──
  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) void video.play();
    else video.pause();
  }, []);

  const skip = useCallback((seconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(
      0,
      Math.min(video.duration || 0, video.currentTime + seconds),
    );
  }, []);

  const toggleMute = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setIsMuted(video.muted);
  }, []);

  const handleVolumeChange = useCallback((value: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.volume = value;
    setVolume(value);
    if (value > 0 && video.muted) {
      video.muted = false;
      setIsMuted(false);
    }
  }, []);

  const toggleLoop = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.loop = !video.loop;
    setIsLooping(video.loop);
  }, []);

  const cyclePlaybackRate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const rates = [0.5, 0.75, 1, 1.25, 1.5, 2];
    const currentIndex = rates.indexOf(playbackRate);
    const nextRate = rates[(currentIndex + 1) % rates.length];
    video.playbackRate = nextRate;
    setPlaybackRate(nextRate);
  }, [playbackRate]);

  const handleSeek = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const video = videoRef.current;
      if (!video || !duration) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const percent = (event.clientX - rect.left) / rect.width;
      video.currentTime = percent * duration;
    },
    [duration],
  );

  const togglePiP = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return;
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      } else {
        await video.requestPictureInPicture();
      }
    } catch {
      /* PiP not supported */
    }
  }, []);

  const toggleFullscreen = useCallback(() => {
    const video = videoRef.current;
    if (video?.requestFullscreen) void video.requestFullscreen();
  }, []);

  // Keyboard navigation for the modal player. The dialog is modal, so the
  // listener is attached to the document while it is open; typing fields and
  // the volume slider keep their native keyboard behaviour.
  useMediaKeyboardShortcuts(null, videoRef, {
    enabled: !!item,
    onTogglePlay: togglePlay,
    onSkip: skip,
    onToggleMute: toggleMute,
    onVolumeChange: handleVolumeChange,
    onToggleFullscreen: toggleFullscreen,
    seekStep: 5,
    volumeStep: 0.05,
  });

  const status = item ? galleryStatusMeta(item.status) : null;

  return (
    <Dialog
      open={!!item}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent
        showCloseButton={false}
        aria-describedby={undefined}
        aria-keyshortcuts="Space K ArrowLeft ArrowRight J L ArrowUp ArrowDown M Home End F"
        className="sm:max-w-[95vw] max-w-[95vw] w-[95vw] max-h-[95vh] p-0 gap-0 overflow-hidden"
      >
        {/* Custom header with proper button layout */}
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
          <DialogTitle className="min-w-0 truncate text-base font-semibold">
            {item?.title}
          </DialogTitle>
          <div className="flex shrink-0 items-center gap-1">
            {item && status && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 text-xs"
                    disabled={isUpdatingStatus}
                    title="Change publishing status"
                  >
                    <span className={cn('size-2 rounded-full', status.dot)} />
                    {status.label}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {GALLERY_STATUS_OPTIONS.map((option) => (
                    <DropdownMenuItem
                      key={option.value}
                      onClick={() => void handleStatusChange(option.value)}
                      disabled={option.value === item.status}
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
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  onClick={handleDownload}
                  disabled={!item}
                >
                  <Download className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Download</TooltipContent>
            </Tooltip>
            {projectHref && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="size-8" asChild>
                    <Link href={projectHref}>
                      <ExternalLink className="size-4" />
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Open Project</TooltipContent>
              </Tooltip>
            )}
            <div className="mx-1 h-5 w-px bg-border" />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  onClick={handleClose}
                >
                  <X className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Close</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Video player area */}
        {item && (
          <div className="relative cursor-pointer bg-black" onClick={togglePlay}>
            <video
              ref={videoRef}
              src={getStreamUrl(item.id)}
              poster={item.thumbnail_url ?? undefined}
              className="w-full object-contain"
              style={{ maxHeight: '80vh' }}
              autoPlay
              playsInline
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onTimeUpdate={(event) =>
                setCurrentTime(event.currentTarget.currentTime)
              }
              onLoadedMetadata={(event) => {
                setDuration(event.currentTarget.duration);
                setVolume(event.currentTarget.volume);
                setIsMuted(event.currentTarget.muted);
              }}
              onEnded={() => setIsPlaying(false)}
            />
            {/* Center play/pause overlay (brief flash on click) */}
            {!isPlaying && currentTime > 0 && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="rounded-full bg-black/50 p-4">
                  <Play className="size-10 text-white" />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Custom controls bar */}
        {item && (
          <div className="border-t bg-background">
            {/* Seek bar */}
            <div
              className="group relative h-2 cursor-pointer bg-muted"
              onClick={handleSeek}
            >
              <div
                className="h-full bg-primary transition-all"
                style={{
                  width:
                    duration > 0
                      ? `${(currentTime / duration) * 100}%`
                      : '0%',
                }}
              />
              {/* Seek thumb */}
              <div
                className="absolute top-1/2 size-3 -translate-y-1/2 rounded-full bg-primary opacity-0 transition-opacity group-hover:opacity-100"
                style={{
                  left:
                    duration > 0
                      ? `calc(${(currentTime / duration) * 100}% - 6px)`
                      : '0',
                }}
              />
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between px-3 py-2">
              {/* Left: play controls */}
              <div className="flex items-center gap-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() => skip(-10)}
                    >
                      <SkipBack className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>-10s</TooltipContent>
                </Tooltip>

                <Button
                  variant="ghost"
                  size="icon"
                  className="size-9"
                  onClick={togglePlay}
                >
                  {isPlaying ? (
                    <Pause className="size-5" />
                  ) : (
                    <Play className="size-5" />
                  )}
                </Button>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() => skip(10)}
                    >
                      <SkipForward className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>+10s</TooltipContent>
                </Tooltip>

                {/* Volume */}
                <div className="ml-2 flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    onClick={toggleMute}
                  >
                    {isMuted || volume === 0 ? (
                      <VolumeX className="size-4" />
                    ) : (
                      <Volume2 className="size-4" />
                    )}
                  </Button>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={isMuted ? 0 : volume}
                    onChange={(event) =>
                      handleVolumeChange(parseFloat(event.target.value))
                    }
                    className="h-1 w-20 cursor-pointer accent-primary"
                  />
                </div>

                {/* Time display */}
                <span className="ml-3 text-xs tabular-nums text-muted-foreground">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>
              </div>

              {/* Right: extra controls */}
              <div className="flex items-center gap-1">
                {/* Playback speed */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 text-xs tabular-nums"
                      onClick={cyclePlaybackRate}
                    >
                      {playbackRate}x
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Playback Speed</TooltipContent>
                </Tooltip>

                {/* Loop */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn('size-8', isLooping && 'text-primary')}
                      onClick={toggleLoop}
                    >
                      <Repeat className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isLooping ? 'Loop: On' : 'Loop: Off'}
                  </TooltipContent>
                </Tooltip>

                {/* PiP */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={togglePiP}
                    >
                      <PictureInPicture2 className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Picture in Picture</TooltipContent>
                </Tooltip>

                {/* Fullscreen */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={toggleFullscreen}
                    >
                      <Maximize2 className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Fullscreen</TooltipContent>
                </Tooltip>
              </div>
            </div>
          </div>
        )}

        {/* Keyboard shortcut hint */}
        {item && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t px-4 py-1.5 text-[11px] text-muted-foreground">
            <span>
              <kbd className="rounded border px-1 font-mono text-[10px]">Space</kbd>{' '}
              play/pause
            </span>
            <span>
              <kbd className="rounded border px-1 font-mono text-[10px]">←</kbd>
              <kbd className="rounded border px-1 font-mono text-[10px]">→</kbd>{' '}
              seek 5s
            </span>
            <span>
              <kbd className="rounded border px-1 font-mono text-[10px]">↑</kbd>
              <kbd className="rounded border px-1 font-mono text-[10px]">↓</kbd>{' '}
              volume
            </span>
            <span>
              <kbd className="rounded border px-1 font-mono text-[10px]">M</kbd>{' '}
              mute
            </span>
            <span>
              <kbd className="rounded border px-1 font-mono text-[10px]">F</kbd>{' '}
              fullscreen
            </span>
          </div>
        )}

        {/* Metadata footer */}
        {item && status && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t px-4 py-2 text-xs text-muted-foreground">
            <span>
              {item.resolution_width}×{item.resolution_height}
            </span>
            <span>{item.framerate} fps</span>
            <span>{item.segment_count} segments</span>
            <span>{formatGalleryFileSize(item.file_size)}</span>
            {item.render_time_seconds != null && (
              <span title="Time spent generating the full video">
                Rendered in {formatGenerationTime(item.render_time_seconds)}
              </span>
            )}
            <Badge variant="outline" className={cn('gap-1 text-[10px]', status.badge)}>
              <span className={cn('size-1.5 rounded-full', status.dot)} />
              {status.label}
            </Badge>
            <span className="ml-auto">{formatAbsoluteDate(item.created_at)}</span>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
