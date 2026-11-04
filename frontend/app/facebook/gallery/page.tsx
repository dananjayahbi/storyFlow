'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { toast } from 'sonner';
import {
  getGalleryItems,
  getStreamUrl,
  getDownloadUrl,
  bulkUpdateGalleryStatus,
  deleteGalleryItem,
  bulkDeleteGalleryItems,
} from '@/lib/api';
import { GalleryItem, RenderingStatus } from '@/lib/types';
import {
  GALLERY_STATUS_OPTIONS,
  filterGalleryItems,
  formatGalleryFileSize,
  galleryStatusMeta,
} from '@/lib/gallery';
import { sectionFromPathname } from '@/lib/section';
import { GalleryAssetCard } from '@/components/GalleryAssetCard';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
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
  Search,
  Trash2,
  CheckSquare,
  XCircle,
} from 'lucide-react';

// ── Utilities ──

function formatAbsoluteDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

// ── Main Component ──

export default function GalleryPage() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<GalleryItem | null>(null);

  // ── Asset-management state ──
  const [statusFilter, setStatusFilter] = useState<RenderingStatus | 'all'>('all');
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'newest' | 'oldest'>('newest');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteTargets, setDeleteTargets] = useState<GalleryItem[] | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  const visibleItems = useMemo(
    () =>
      filterGalleryItems(items, {
        status: statusFilter,
        project: projectFilter,
        query,
        sort,
      }),
    [items, statusFilter, projectFilter, query, sort],
  );

  const projectOptions = useMemo(() => {
    const map = new Map<string, string>();
    items.forEach((item) => map.set(item.project_id, item.project_title));
    return Array.from(map, ([id, title]) => ({ id, title })).sort((a, b) =>
      a.title.localeCompare(b.title),
    );
  }, [items]);

  const allVisibleSelected =
    visibleItems.length > 0 &&
    visibleItems.every((item) => selectedIds.has(item.id));

  const toggleSelection = useCallback((id: string, selected: boolean) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (selected) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (allVisibleSelected) {
        visibleItems.forEach((item) => next.delete(item.id));
      } else {
        visibleItems.forEach((item) => next.add(item.id));
      }
      return next;
    });
  }, [allVisibleSelected, visibleItems]);

  const clearFilters = useCallback(() => {
    setStatusFilter('all');
    setProjectFilter('all');
    setQuery('');
    setSort('newest');
  }, []);

  const handleBulkStatus = useCallback(
    async (status: RenderingStatus) => {
      if (selectedIds.size === 0) return;
      const ids = Array.from(selectedIds);
      setIsMutating(true);
      try {
        await bulkUpdateGalleryStatus(ids, status);
        setItems((previous) =>
          previous.map((item) =>
            ids.includes(item.id)
              ? {
                  ...item,
                  status,
                  status_label: galleryStatusMeta(status).label,
                  published_at:
                    status === 'published'
                      ? new Date().toISOString()
                      : null,
                }
              : item,
          ),
        );
        setSelectedIds(new Set());
        toast.success(
          `${ids.length} rendering${ids.length === 1 ? '' : 's'} marked ${galleryStatusMeta(status).label.toLowerCase()}`,
        );
      } catch {
        toast.error('Could not update the selected renderings.');
      } finally {
        setIsMutating(false);
      }
    },
    [selectedIds],
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTargets?.length) return;
    const ids = deleteTargets.map((item) => item.id);
    setIsMutating(true);
    try {
      if (ids.length === 1) {
        await deleteGalleryItem(ids[0]);
      } else {
        await bulkDeleteGalleryItems(ids);
      }
      setItems((previous) => previous.filter((item) => !ids.includes(item.id)));
      if (selectedItem && ids.includes(selectedItem.id)) {
        setSelectedItem(null);
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);
        setPlaybackRate(1);
      }
      setSelectedIds((previous) => {
        const next = new Set(previous);
        ids.forEach((id) => next.delete(id));
        return next;
      });
      toast.success(
        `${ids.length} rendering${ids.length === 1 ? '' : 's'} deleted`,
      );
    } catch {
      toast.error('Could not delete the selected rendering(s).');
    } finally {
      setIsMutating(false);
      setDeleteTargets(null);
    }
  }, [deleteTargets, selectedItem]);

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
      const data = await getGalleryItems(section);
      setItems(data);
    } catch {
      setError('Failed to load gallery. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [section]);

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

  const hasFilters =
    statusFilter !== 'all' ||
    projectFilter !== 'all' ||
    query.trim().length > 0 ||
    sort !== 'newest';

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Gallery</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Manage every rendering produced by this account&apos;s projects
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="hidden sm:inline-flex">
            {items.length} asset{items.length === 1 ? '' : 's'}
          </Badge>
          <Button variant="outline" size="sm" onClick={fetchGallery} disabled={loading}>
            <RefreshCw className={`size-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter bar */}
      <Card>
        <CardContent className="p-3 sm:p-4 space-y-3">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
            <div className="relative min-w-[200px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search video or project title…"
                className="h-9 pl-9"
              />
            </div>

            <Select
              value={statusFilter}
              onValueChange={(value) =>
                setStatusFilter(value as RenderingStatus | 'all')
              }
            >
              <SelectTrigger className="h-9 w-full lg:w-[170px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {GALLERY_STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={projectFilter} onValueChange={setProjectFilter}>
              <SelectTrigger className="h-9 w-full lg:w-[210px]">
                <SelectValue placeholder="Project" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All projects</SelectItem>
                {projectOptions.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={sort}
              onValueChange={(value) => setSort(value as 'newest' | 'oldest')}
            >
              <SelectTrigger className="h-9 w-full lg:w-[140px]">
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Newest first</SelectItem>
                <SelectItem value="oldest">Oldest first</SelectItem>
              </SelectContent>
            </Select>

            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                className="h-9 shrink-0"
                onClick={clearFilters}
              >
                <XCircle className="mr-1.5 size-4" />
                Clear
              </Button>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={toggleSelectAll}
                disabled={visibleItems.length === 0}
              >
                <CheckSquare className="mr-1.5 size-3.5" />
                {allVisibleSelected ? 'Deselect all' : 'Select all'}
              </Button>
              <span>
                {visibleItems.length} of {items.length} shown
              </span>
            </div>

            {selectedIds.size > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 rounded-lg border bg-muted/40 px-2 py-1.5">
                <span className="px-1 text-xs font-medium">
                  {selectedIds.size} selected
                </span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      disabled={isMutating}
                    >
                      Change status
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {GALLERY_STATUS_OPTIONS.map((option) => (
                      <DropdownMenuItem
                        key={option.value}
                        onClick={() => handleBulkStatus(option.value)}
                      >
                        <span
                          className={`mr-2 size-2 rounded-full ${galleryStatusMeta(option.value).dot}`}
                        />
                        {option.label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  size="sm"
                  variant="destructive"
                  className="h-7 text-xs"
                  disabled={isMutating}
                  onClick={() =>
                    setDeleteTargets(
                      items.filter((item) => selectedIds.has(item.id)),
                    )
                  }
                >
                  <Trash2 className="mr-1.5 size-3.5" />
                  Delete
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => setSelectedIds(new Set())}
                >
                  Clear
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

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
        <div className="columns-2 sm:columns-3 lg:columns-4 xl:columns-5 2xl:columns-6 gap-3 [column-fill:_balance]">
          {Array.from({ length: 12 }).map((_, i) => (
            <Card key={i} className="overflow-hidden break-inside-avoid mb-3">
              <Skeleton className={`w-full ${i % 3 === 1 ? 'aspect-[9/16]' : 'aspect-video'}`} />
              <CardContent className="pt-2.5 pb-3">
                <Skeleton className="h-4 w-3/4 mb-2" />
                <Skeleton className="h-3 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty state — no assets at all */}
      {!loading && !error && items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <MonitorPlay className="size-16 mb-4 opacity-30" />
          <p className="text-lg font-medium">No rendered videos yet</p>
          <p className="text-sm mt-1">Render a project to see it appear here</p>
          <Button asChild variant="outline" size="sm" className="mt-4">
            <Link href={`/${section}/projects`}>Go to Projects</Link>
          </Button>
        </div>
      )}

      {/* Empty state — filters exclude everything */}
      {!loading && items.length > 0 && visibleItems.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Search className="size-12 mb-3 opacity-30" />
          <p className="text-base font-medium">No assets match these filters</p>
          <p className="mt-1 text-sm">Try another status, project or search term</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={clearFilters}>
            Clear filters
          </Button>
        </div>
      )}

      {/* Asset grid — masonry layout for mixed aspect ratios */}
      {!loading && visibleItems.length > 0 && (
        <div className="columns-2 sm:columns-3 lg:columns-4 xl:columns-5 2xl:columns-6 gap-3 [column-fill:_balance]">
          {visibleItems.map((item) => (
            <GalleryAssetCard
              key={item.id}
              item={item}
              selected={selectedIds.has(item.id)}
              onSelectedChange={(selected) => toggleSelection(item.id, selected)}
              onOpen={() => setSelectedItem(item)}
              onDownload={(event) => handleDownload(item, event)}
              onDelete={() => setDeleteTargets([item])}
            />
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
                    <Link href={`/${section}/projects/${selectedItem?.project_id}`}>
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
              <span>{formatGalleryFileSize(selectedItem.file_size)}</span>
              <span>{galleryStatusMeta(selectedItem.status).label}</span>
              <span className="ml-auto">{formatAbsoluteDate(selectedItem.created_at)}</span>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog
        open={!!deleteTargets}
        onOpenChange={(open) => {
          if (!open && !isMutating) setDeleteTargets(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete{' '}
              {deleteTargets && deleteTargets.length === 1
                ? `"${deleteTargets[0].title}"`
                : `${deleteTargets?.length ?? 0} renderings`}
              ?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the rendered video file
              {deleteTargets && deleteTargets.length > 1 ? 's' : ''} from the
              gallery and storage. The project, script and segments stay intact
              and can be rendered again later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMutating}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isMutating}
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={(event) => {
                event.preventDefault();
                void confirmDelete();
              }}
            >
              {isMutating ? 'Deleting…' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
