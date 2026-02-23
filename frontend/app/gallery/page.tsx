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
  DialogHeader,
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
  const videoRef = useRef<HTMLVideoElement>(null);

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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <Skeleton className="aspect-video w-full" />
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

      {/* Video grid */}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <Card
              key={item.id}
              className="overflow-hidden cursor-pointer group hover:ring-2 hover:ring-primary/20 transition-all"
              onClick={() => setSelectedItem(item)}
            >
              {/* Video preview */}
              <div className="relative aspect-video bg-black">
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
      <Dialog open={!!selectedItem} onOpenChange={(open) => !open && setSelectedItem(null)}>
        <DialogContent className="max-w-4xl w-full p-0 gap-0 overflow-hidden">
          <DialogHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <DialogTitle className="truncate pr-4">
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
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      asChild
                    >
                      <Link href={`/projects/${selectedItem?.id}`}>
                        <ExternalLink className="size-4" />
                      </Link>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Open Project</TooltipContent>
                </Tooltip>
              </div>
            </div>
          </DialogHeader>

          {/* Video player */}
          {selectedItem && (
            <div className="bg-black">
              <video
                ref={videoRef}
                src={getStreamUrl(selectedItem.id)}
                className="w-full max-h-[70vh] object-contain"
                controls
                autoPlay
                playsInline
              />
            </div>
          )}

          {/* Metadata footer */}
          {selectedItem && (
            <div className="p-4 pt-2 flex items-center gap-4 text-xs text-muted-foreground border-t">
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
