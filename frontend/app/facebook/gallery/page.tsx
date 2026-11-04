'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { toast } from 'sonner';
import {
  getGalleryItems,
  getDownloadUrl,
  bulkUpdateGalleryStatus,
  deleteGalleryItem,
  bulkDeleteGalleryItems,
  updateGalleryItemStatus,
} from '@/lib/api';
import { GalleryItem, RenderingStatus } from '@/lib/types';
import {
  GALLERY_STATUS_OPTIONS,
  filterGalleryItems,
  galleryStatusMeta,
} from '@/lib/gallery';
import { sectionFromPathname } from '@/lib/section';
import { GalleryAssetCard } from '@/components/GalleryAssetCard';
import { GalleryVideoPlayerDialog } from '@/components/GalleryVideoPlayerDialog';
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
  Film,
  RefreshCw,
  MonitorPlay,
  Search,
  Trash2,
  CheckSquare,
  XCircle,
} from 'lucide-react';

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

  const handleStatusChange = useCallback(
    async (item: GalleryItem, status: RenderingStatus) => {
      if (status === item.status) return;
      setIsMutating(true);
      try {
        await updateGalleryItemStatus(item.id, status);
        const updated: GalleryItem = {
          ...item,
          status,
          status_label: galleryStatusMeta(status).label,
          published_at:
            status === 'published' ? new Date().toISOString() : null,
        };
        setItems((previous) =>
          previous.map((entry) => (entry.id === item.id ? updated : entry)),
        );
        setSelectedItem((previous) =>
          previous && previous.id === item.id ? updated : previous,
        );
        toast.success(
          `Marked "${item.title}" ${galleryStatusMeta(status).label.toLowerCase()}`,
        );
      } catch {
        toast.error('Could not update this rendering\u2019s status.');
      } finally {
        setIsMutating(false);
      }
    },
    [],
  );

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

      {/* Filter bar — compact, single row on desktop */}
      <Card className="gap-0 py-0">
        <CardContent className="p-2 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[180px] flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search video or project title…"
                className="h-8 pl-8 text-sm"
              />
            </div>

            <Select
              value={statusFilter}
              onValueChange={(value) =>
                setStatusFilter(value as RenderingStatus | 'all')
              }
            >
              <SelectTrigger className="h-8 w-[150px] text-xs">
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
              <SelectTrigger className="h-8 w-[180px] text-xs">
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
              <SelectTrigger className="h-8 w-[130px] text-xs">
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
                className="h-8 shrink-0 px-2 text-xs"
                onClick={clearFilters}
              >
                <XCircle className="mr-1 size-3.5" />
                Clear
              </Button>
            )}

            <div className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
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
              <span className="whitespace-nowrap tabular-nums">
                {visibleItems.length}/{items.length}
              </span>
            </div>
          </div>

          {selectedIds.size > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 rounded-md border bg-muted/40 px-2 py-1">
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
              onStatusChange={(status) =>
                void handleStatusChange(item, status)
              }
            />
          ))}
        </div>
      )}

      {/* Video Player Dialog */}
      <GalleryVideoPlayerDialog
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onItemUpdated={(updated) => {
          setItems((previous) =>
            previous.map((entry) =>
              entry.id === updated.id ? updated : entry,
            ),
          );
          setSelectedItem(updated);
        }}
        projectHref={
          selectedItem ? `/${section}/projects/${selectedItem.project_id}` : undefined
        }
      />

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
