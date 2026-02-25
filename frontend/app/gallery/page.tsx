'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { getGalleryItems, getStreamUrl, getDownloadUrl } from '@/lib/api';
import { GalleryItem } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Film,
  Download,
  Play,
  RefreshCw,
  Clock,
  Maximize2,
  MonitorPlay,
  X,
  ExternalLink,
  Volume2,
  VolumeX,
  Pause,
  SkipBack,
  SkipForward,
  Repeat,
  PictureInPicture2,
} from 'lucide-react';

// ── Utilities ──

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMonth = Math.floor(diffDay / 30);
  if (diffMonth < 12) return `${diffMonth}mo ago`;
  const diffYear = Math.floor(diffDay / 365);
  return `${diffYear}y ago`;
}

function formatAbsoluteDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

// ── Main Component ──

export default function GalleryPage() {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<GalleryItem | null>(null);

  // ── Video player state ──
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);

  const fetchGallery = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGalleryItems();
      setItems(data);
    } catch {
      setError('Failed to load gallery. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGallery();
  }, [fetchGallery]);

  const handleDownload = useCallback((item: GalleryItem, e?: React.MouseEvent) => {
    e?.stopPropagation();
    const url = getDownloadUrl(item.id);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${item.title}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, []);

  // ── Player controls ──
  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { v.play(); } else { v.pause(); }
  }, []);

  const skip = useCallback((seconds: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(v.duration, v.currentTime + seconds));
  }, []);

  const toggleMute = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setIsMuted(v.muted);
  }, []);

  const handleVolumeChange = useCallback((val: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.volume = val;
    setVolume(val);
    if (val > 0 && v.muted) { v.muted = false; setIsMuted(false); }
  }, []);

  const toggleLoop = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.loop = !v.loop;
    setIsLooping(v.loop);
  }, []);

  const cyclePlaybackRate = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    const rates = [0.5, 0.75, 1, 1.25, 1.5, 2];
    const currentIdx = rates.indexOf(playbackRate);
    const nextIdx = (currentIdx + 1) % rates.length;
    const newRate = rates[nextIdx];
    v.playbackRate = newRate;
    setPlaybackRate(newRate);
  }, [playbackRate]);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const v = videoRef.current;
    if (!v || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    v.currentTime = pct * duration;
  }, [duration]);

  const togglePiP = useCallback(async () => {
    const v = videoRef.current;
    if (!v) return;
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      } else {
        await v.requestPictureInPicture();
      }
    } catch { /* PiP not supported */ }
  }, []);

  const toggleFullscreen = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.requestFullscreen) { v.requestFullscreen(); }
  }, []);

  const handleClosePlayer = useCallback(() => {
    const v = videoRef.current;
    if (v) { v.pause(); v.src = ''; }
    setSelectedItem(null);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setPlaybackRate(1);
  }, []);

  function formatTime(seconds: number): string {
    if (!isFinite(seconds) || seconds < 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Gallery</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Browse and download your rendered videos
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchGallery} disabled={loading}>
          <RefreshCw className={`size-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <Film className="size-4" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {loading && (
        <div className="columns-1 md:columns-2 lg:columns-3 gap-4 [column-fill:_balance]">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="overflow-hidden break-inside-avoid mb-4">
              <Skeleton className={`w-full ${i % 3 === 1 ? 'aspect-[9/16]' : 'aspect-video'}`} />
              <CardContent className="pt-4">
                <Skeleton className="h-5 w-3/4 mb-2" />
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <MonitorPlay className="size-16 mb-4 opacity-30" />
          <p className="text-lg font-medium">No rendered videos yet</p>
          <p className="text-sm mt-1">Render a project to see it appear here</p>
          <Button asChild variant="outline" size="sm" className="mt-4">
            <Link href="/projects">Go to Projects</Link>
          </Button>
        </div>
      )}

      {/* Video grid — masonry layout for mixed aspect ratios */}
      {!loading && items.length > 0 && (
        <div className="columns-1 md:columns-2 lg:columns-3 gap-4 [column-fill:_balance]">
          {items.map((item) => (
            <Card
              key={item.id}
              className="overflow-hidden cursor-pointer group hover:ring-2 hover:ring-primary/20 transition-all break-inside-avoid mb-4"
              onClick={() => setSelectedItem(item)}
            >
              {/* Video preview */}
              <div
                className="relative bg-black"
                style={{
                  aspectRatio: `${item.resolution_width} / ${item.resolution_height}`,
                }}
              >
                <video
                  src={getStreamUrl(item.id)}
                  className="w-full h-full object-contain"
                  preload="metadata"
                  muted
                  playsInline
                  onMouseEnter={(e) => {
                    const v = e.currentTarget;
                    v.currentTime = 0;
                    v.play().catch(() => {});
                  }}
                  onMouseLeave={(e) => {
                    const v = e.currentTarget;
                    v.pause();
                    v.currentTime = 0;
                  }}
                />
                {/* Play overlay */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  <div className="bg-white/90 dark:bg-black/70 rounded-full p-3">
                    <Play className="size-6 text-foreground" />
                  </div>
                </div>
                {/* Resolution badge */}
                <div className="absolute top-2 right-2">
                  <Badge variant="outline" className="bg-black/60 text-white border-white/20 text-xs">
                    {item.resolution_width}×{item.resolution_height}
                  </Badge>
                </div>
              </div>

              {/* Info */}
              <CardContent className="pt-3 pb-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-medium truncate">{item.title}</h3>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="flex items-center gap-1">
                            <Clock className="size-3" />
                            {formatRelativeTime(item.updated_at)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">{formatAbsoluteDate(item.updated_at)}</p>
                        </TooltipContent>
                      </Tooltip>
                      <span>{item.segment_count} segments</span>
                      <span>{formatFileSize(item.file_size)}</span>
                    </div>
                  </div>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 shrink-0"
                        onClick={(e) => handleDownload(item, e)}
                      >
                        <Download className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Download</TooltipContent>
                  </Tooltip>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Video Player Dialog */}
      <Dialog open={!!selectedItem} onOpenChange={(open) => { if (!open) handleClosePlayer(); }}>
        <DialogContent
          showCloseButton={false}
          className="sm:max-w-[95vw] max-w-[95vw] w-[95vw] max-h-[95vh] p-0 gap-0 overflow-hidden"
        >
          {/* Custom header with proper button layout */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <DialogTitle className="truncate text-base font-semibold pr-4">
              {selectedItem?.title}
            </DialogTitle>
            <div className="flex items-center gap-1 shrink-0">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    onClick={() => selectedItem && handleDownload(selectedItem)}
                  >
                    <Download className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Download</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="size-8" asChild>
                    <Link href={`/projects/${selectedItem?.id}`}>
                      <ExternalLink className="size-4" />
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Open Project</TooltipContent>
              </Tooltip>
              <div className="w-px h-5 bg-border mx-1" />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    onClick={handleClosePlayer}
                  >
                    <X className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Close</TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Video player area */}
          {selectedItem && (
            <div
              className="relative bg-black cursor-pointer"
              onClick={togglePlay}
            >
              <video
                ref={videoRef}
                src={getStreamUrl(selectedItem.id)}
                className="w-full object-contain"
                style={{ maxHeight: '80vh' }}
                autoPlay
                playsInline
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                onLoadedMetadata={(e) => {
                  setDuration(e.currentTarget.duration);
                  setVolume(e.currentTarget.volume);
                  setIsMuted(e.currentTarget.muted);
                }}
                onEnded={() => setIsPlaying(false)}
              />
              {/* Center play/pause overlay (brief flash on click) */}
              {!isPlaying && currentTime > 0 && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="bg-black/50 rounded-full p-4">
                    <Play className="size-10 text-white" />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Custom controls bar */}
          {selectedItem && (
            <div className="border-t bg-background">
              {/* Seek bar */}
              <div
                className="h-2 bg-muted cursor-pointer group relative"
                onClick={handleSeek}
              >
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: duration > 0 ? `${(currentTime / duration) * 100}%` : '0%' }}
                />
                {/* Seek thumb */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 size-3 bg-primary rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ left: duration > 0 ? `calc(${(currentTime / duration) * 100}% - 6px)` : '0' }}
                />
              </div>

              {/* Controls */}
              <div className="flex items-center justify-between px-3 py-2">
                {/* Left: play controls */}
                <div className="flex items-center gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8" onClick={() => skip(-10)}>
                        <SkipBack className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>-10s</TooltipContent>
                  </Tooltip>

                  <Button variant="ghost" size="icon" className="size-9" onClick={togglePlay}>
                    {isPlaying ? <Pause className="size-5" /> : <Play className="size-5" />}
                  </Button>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8" onClick={() => skip(10)}>
                        <SkipForward className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>+10s</TooltipContent>
                  </Tooltip>

                  {/* Volume */}
                  <div className="flex items-center gap-1 ml-2">
                    <Button variant="ghost" size="icon" className="size-8" onClick={toggleMute}>
                      {isMuted || volume === 0 ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
                    </Button>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={isMuted ? 0 : volume}
                      onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                      className="w-20 h-1 accent-primary cursor-pointer"
                    />
                  </div>

                  {/* Time display */}
                  <span className="text-xs text-muted-foreground ml-3 tabular-nums">
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
                        className="text-xs h-8 px-2 tabular-nums"
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
                        className={`size-8 ${isLooping ? 'text-primary' : ''}`}
                        onClick={toggleLoop}
                      >
                        <Repeat className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>{isLooping ? 'Loop: On' : 'Loop: Off'}</TooltipContent>
                  </Tooltip>

                  {/* PiP */}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8" onClick={togglePiP}>
                        <PictureInPicture2 className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Picture in Picture</TooltipContent>
                  </Tooltip>

                  {/* Fullscreen */}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8" onClick={toggleFullscreen}>
                        <Maximize2 className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Fullscreen</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </div>
          )}

          {/* Metadata footer */}
          {selectedItem && (
            <div className="px-4 py-2 flex items-center gap-4 text-xs text-muted-foreground border-t">
              <span>{selectedItem.resolution_width}×{selectedItem.resolution_height}</span>
              <span>{selectedItem.framerate} fps</span>
              <span>{selectedItem.segment_count} segments</span>
              <span>{formatFileSize(selectedItem.file_size)}</span>
              <span className="ml-auto">{formatAbsoluteDate(selectedItem.updated_at)}</span>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
