'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  bulkDeleteGalleryItems,
  bulkUpdateGalleryStatus,
  deleteGalleryItem,
  getDownloadUrl,
  getGalleryItems,
} from '@/lib/api';
import { GalleryItem, RenderingStatus } from '@/lib/types';
import {
  GALLERY_STATUS_OPTIONS,
  galleryStatusMeta,
} from '@/lib/gallery';
import { GalleryAssetCard } from '@/components/GalleryAssetCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
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
  CheckSquare,
  Film,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProjectGalleryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  projectTitle?: string;
  /** Called after a deletion so the project page can refresh its counters. */
  onChanged?: () => void;
}

/**
 * Full-viewport gallery for one project.  A project can be rendered many
 * times; this modal shows every version, regardless of status, and allows
 * deleting individual renderings without touching the project/script.
 */
export function ProjectGalleryModal({
  open,
  onOpenChange,
  projectId,
  projectTitle,
  onChanged,
}: ProjectGalleryModalProps) {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteTargets, setDeleteTargets] = useState<GalleryItem[] | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  const fetchItems = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getGalleryItems(undefined, { project: projectId });
      setItems(data);
      setSelectedIds(new Set());
    } catch {
      setError('Failed to load this project\u2019s renderings.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (open) void fetchItems();
  }, [open, fetchItems]);

  const allSelected =
    items.length > 0 && items.every((item) => selectedIds.has(item.id));

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
      if (allSelected) items.forEach((item) => next.delete(item.id));
      else items.forEach((item) => next.add(item.id));
      return next;
    });
  }, [allSelected, items]);

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
                }
              : item,
          ),
        );
        setSelectedIds(new Set());
        toast.success(
          `${ids.length} rendering${ids.length === 1 ? '' : 's'} updated`,
        );
        onChanged?.();
      } catch {
        toast.error('Could not update the selected renderings.');
      } finally {
        setIsMutating(false);
      }
    },
    [selectedIds, onChanged],
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTargets?.length) return;
    const ids = deleteTargets.map((item) => item.id);
    setIsMutating(true);
    try {
      if (ids.length === 1) await deleteGalleryItem(ids[0]);
      else await bulkDeleteGalleryItems(ids);
      setItems((previous) => previous.filter((item) => !ids.includes(item.id)));
      setSelectedIds((previous) => {
        const next = new Set(previous);
        ids.forEach((id) => next.delete(id));
        return next;
      });
      toast.success(
        `${ids.length} rendering${ids.length === 1 ? '' : 's'} deleted`,
      );
      onChanged?.();
    } catch {
      toast.error('Could not delete the selected rendering(s).');
    } finally {
      setIsMutating(false);
      setDeleteTargets(null);
    }
  }, [deleteTargets, onChanged]);

  const handleDownload = useCallback(
    (item: GalleryItem, event?: React.MouseEvent) => {
      event?.stopPropagation();
      const anchor = document.createElement('a');
      anchor.href = getDownloadUrl(item.id);
      anchor.download = `${item.title}.mp4`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    },
    [],
  );

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((item) => {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
    });
    return counts;
  }, [items]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="m-0 grid h-screen max-h-screen w-screen max-w-none grid-rows-[auto_auto_minmax(0,1fr)] gap-0 overflow-hidden rounded-none border-0 p-0 sm:max-w-none"
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Film className="size-5" />
            </div>
            <div className="min-w-0">
              <DialogTitle className="truncate text-base font-semibold">
                Project gallery
              </DialogTitle>
              <p className="truncate text-xs text-muted-foreground">
                {projectTitle ? `${projectTitle} · ` : ''}
                {items.length} rendering{items.length === 1 ? '' : 's'}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void fetchItems()}
              disabled={loading}
            >
              <RefreshCw
                className={cn('mr-1.5 size-4', loading && 'animate-spin')}
              />
              Refresh
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onOpenChange(false)}
              aria-label="Close project gallery"
            >
              <X className="size-5" />
            </Button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-muted/20 px-4 py-2 sm:px-6">
          <div className="flex flex-wrap items-center gap-2">
            {GALLERY_STATUS_OPTIONS.map((option) => (
              <Badge
                key={option.value}
                variant="outline"
                className={cn('gap-1 text-[10px]', galleryStatusMeta(option.value).badge)}
              >
                <span
                  className={cn('size-1.5 rounded-full', galleryStatusMeta(option.value).dot)}
                />
                {option.label} {statusCounts[option.value] ?? 0}
              </Badge>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={toggleSelectAll}
              disabled={items.length === 0}
            >
              <CheckSquare className="mr-1.5 size-3.5" />
              {allSelected ? 'Deselect all' : 'Select all'}
            </Button>
            {selectedIds.size > 0 && (
              <>
                <span className="text-xs font-medium">
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
              </>
            )}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto bg-background p-4 sm:p-6">
          {error && (
            <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {loading && (
            <div className="columns-2 sm:columns-3 lg:columns-4 xl:columns-5 gap-3">
              {Array.from({ length: 8 }).map((_, index) => (
                <div
                  key={index}
                  className="mb-3 break-inside-avoid overflow-hidden rounded-xl border"
                >
                  <Skeleton className="aspect-video w-full" />
                  <div className="space-y-2 p-3">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center py-20 text-muted-foreground">
              <Film className="mb-4 size-14 opacity-25" />
              <p className="text-lg font-medium">No renderings for this project</p>
              <p className="mt-1 text-sm">
                Export the project to create the first gallery asset.
              </p>
            </div>
          )}

          {!loading && items.length > 0 && (
            <div className="columns-2 sm:columns-3 lg:columns-4 xl:columns-5 2xl:columns-6 gap-3 [column-fill:_balance]">
              {items.map((item) => (
                <GalleryAssetCard
                  key={item.id}
                  item={item}
                  showProject={false}
                  selected={selectedIds.has(item.id)}
                  onSelectedChange={(selected) =>
                    toggleSelection(item.id, selected)
                  }
                  onDownload={(event) => handleDownload(item, event)}
                  onDelete={() => setDeleteTargets([item])}
                />
              ))}
            </div>
          )}
        </div>

        {/* Delete confirmation */}
        <AlertDialog
          open={!!deleteTargets}
          onOpenChange={(nextOpen) => {
            if (!nextOpen && !isMutating) setDeleteTargets(null);
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
                gallery and storage. The project and its script stay intact.
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
      </DialogContent>
    </Dialog>
  );
}
