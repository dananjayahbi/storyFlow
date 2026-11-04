'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  getProjectRenderReadiness,
  startRender,
  getRenderStatus,
  cancelRender,
} from '@/lib/api';
import { sectionFromPathname } from '@/lib/section';
import { withAccount } from '@/lib/account';
import { useAccountId } from '@/lib/useAccountId';
import { Project } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Layers,
  Play,
  Square,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  Info,
  ImageOff,
  Volume2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';

// ── Types ──

type ReadinessStatus = 'checking' | 'ready' | 'not-ready' | 'processing';

interface ProjectReadiness {
  id: string;
  title: string;
  status: Project['status'];
  segmentCount: number;
  readiness: ReadinessStatus;
  missingImages: number;
  missingAudio: number;
  emptySegments: boolean;
}

type QueueItemStatus =
  | 'queued'
  | 'rendering'
  | 'completed'
  | 'failed'
  | 'cancelled';

interface QueueItem {
  projectId: string;
  title: string;
  status: QueueItemStatus;
  progress: number;
  currentPhase: string;
  currentSegment: number;
  totalSegments: number;
  error: string | null;
}

// ── Constants ──

const POLL_INTERVAL = 3000;

// ── Helper functions ──

function getReadinessBadge(item: ProjectReadiness) {
  switch (item.readiness) {
    case 'checking':
      return { label: 'Checking…', className: 'bg-muted text-muted-foreground border-muted' };
    case 'ready':
      return { label: 'Ready', className: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30' };
    case 'processing':
      return { label: 'Rendering', className: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30' };
    case 'not-ready':
      return { label: 'Not Ready', className: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30' };
  }
}

function getQueueStatusBadge(status: QueueItemStatus) {
  switch (status) {
    case 'queued':
      return { label: 'Queued', className: 'bg-muted text-muted-foreground border-muted' };
    case 'rendering':
      return { label: 'Rendering', className: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30' };
    case 'completed':
      return { label: 'Completed', className: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30' };
    case 'failed':
      return { label: 'Failed', className: 'bg-destructive/15 text-destructive border-destructive/30' };
    case 'cancelled':
      return { label: 'Cancelled', className: 'bg-muted text-muted-foreground border-muted' };
  }
}

function getIssueTooltip(item: ProjectReadiness): string {
  const issues: string[] = [];
  if (item.emptySegments) issues.push('No segments');
  if (item.missingImages > 0) issues.push(`${item.missingImages} segment(s) missing images`);
  if (item.missingAudio > 0) issues.push(`${item.missingAudio} segment(s) missing audio`);
  if (item.readiness === 'processing') issues.push('Currently rendering');
  return issues.join('\n');
}

// ── Main Component ──

export default function BulkCreatePage() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);
  const accountId = useAccountId(section);
  const projectHref = useCallback(
    (projectId: string) =>
      withAccount(`/${section}/projects/${projectId}`, accountId),
    [section, accountId],
  );

  // ── State ──
  const [projectItems, setProjectItems] = useState<ProjectReadiness[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  const pollTimersRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());
  const cancelledRef = useRef(false);
  const mountedRef = useRef(true);

  // ── Derived state ──
  const readyProjects = useMemo(
    () => projectItems.filter((p) => p.readiness === 'ready'),
    [projectItems]
  );

  const selectedReadyCount = useMemo(
    () => readyProjects.filter((p) => selectedIds.has(p.id)).length,
    [readyProjects, selectedIds]
  );

  const allReadySelected = useMemo(
    () => readyProjects.length > 0 && readyProjects.every((p) => selectedIds.has(p.id)),
    [readyProjects, selectedIds]
  );

  const queueCompleted = useMemo(
    () => queue.length > 0 && queue.every((q) => ['completed', 'failed', 'cancelled'].includes(q.status)),
    [queue]
  );

  // ── Cleanup poll timers on unmount ──
  useEffect(() => {
    mountedRef.current = true;
    const timers = pollTimersRef.current;
    return () => {
      mountedRef.current = false;
      timers.forEach((timer) => clearInterval(timer));
      timers.clear();
    };
  }, []);

  // ── Fetch the backend's real render preflight for this account ──
  const fetchAndValidate = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) setLoading(true);
    setError(null);

    try {
      const readiness = await getProjectRenderReadiness(section);

      // The endpoint returns every project; keep only statuses this page can
      // act on (renderable drafts/completed/failed) plus in-flight renders.
      const items: ProjectReadiness[] = readiness
        .filter((item) => item.renderable || item.is_processing)
        .map((item) => ({
          id: item.project_id,
          title: item.title,
          status: item.status,
          segmentCount: item.segment_count,
          readiness: item.is_processing
            ? ('processing' as const)
            : item.ready
              ? ('ready' as const)
              : ('not-ready' as const),
          missingImages: item.missing_images.length,
          missingAudio: item.missing_audio.length,
          emptySegments: item.segment_count === 0,
        }));

      if (!mountedRef.current) return;
      setProjectItems(items);
      // Drop selections that are no longer ready after a refresh.
      setSelectedIds((previous) => {
        const readyIds = new Set(
          items.filter((item) => item.readiness === 'ready').map((item) => item.id),
        );
        return new Set(Array.from(previous).filter((id) => readyIds.has(id)));
      });
    } catch {
      if (mountedRef.current) {
        setError('Failed to load render readiness. Please try again.');
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [section]);

  useEffect(() => {
    fetchAndValidate();
  }, [fetchAndValidate]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (allReadySelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(readyProjects.map((p) => p.id)));
    }
  }, [allReadySelected, readyProjects]);

  // ── Start bulk render ──
  const startBulkRender = useCallback(async () => {
    const selected = readyProjects.filter((p) => selectedIds.has(p.id));
    if (selected.length === 0) return;

    cancelledRef.current = false;
    setIsCancelling(false);
    setIsRunning(true);

    // Initialize queue
    const initialQueue: QueueItem[] = selected.map((p) => ({
      projectId: p.id,
      title: p.title,
      status: 'queued' as const,
      progress: 0,
      currentPhase: 'Waiting',
      currentSegment: 0,
      totalSegments: p.segmentCount,
      error: null,
    }));

    setQueue(initialQueue);
    setSelectedIds(new Set()); // Clear selection

    // Process sequentially
    for (let i = 0; i < initialQueue.length; i++) {
      const queueItem = initialQueue[i];

      // Check if cancelled
      if (cancelledRef.current) {
        // Mark remaining as cancelled
        setQueue((prev) =>
          prev.map((item, idx) =>
            idx >= i && item.status === 'queued'
              ? { ...item, status: 'cancelled' as const, currentPhase: 'Cancelled' }
              : item
          )
        );
        break;
      }

      // Mark current as rendering
      setQueue((prev) =>
        prev.map((item) =>
          item.projectId === queueItem.projectId
            ? { ...item, status: 'rendering' as const, currentPhase: 'Starting…' }
            : item
        )
      );

      try {
        const result = await startRender(queueItem.projectId);

        // Update with task info
        setQueue((prev) =>
          prev.map((item) =>
            item.projectId === queueItem.projectId
              ? {
                  ...item,
                  status: 'rendering' as const,
                  totalSegments: result.total_segments,
                  currentPhase: 'Rendering',
                }
              : item
          )
        );

        // Poll and wait for completion
        await new Promise<void>((resolve) => {
          const timer = setInterval(async () => {
            if (cancelledRef.current) {
              clearInterval(timer);
              pollTimersRef.current.delete(queueItem.projectId);
              // Try to cancel on the backend
              try {
                await cancelRender(queueItem.projectId);
              } catch { /* best effort */ }
              setQueue((prev) =>
                prev.map((item) =>
                  item.projectId === queueItem.projectId && item.status === 'rendering'
                    ? { ...item, status: 'cancelled' as const, currentPhase: 'Cancelled' }
                    : item
                )
              );
              resolve();
              return;
            }

            try {
              const status = await getRenderStatus(queueItem.projectId);

              if (status.status === 'COMPLETED') {
                clearInterval(timer);
                pollTimersRef.current.delete(queueItem.projectId);
                setQueue((prev) =>
                  prev.map((item) =>
                    item.projectId === queueItem.projectId
                      ? { ...item, status: 'completed' as const, progress: 100, currentPhase: 'Done' }
                      : item
                  )
                );
                resolve();
                return;
              }

              if (status.status === 'FAILED') {
                clearInterval(timer);
                pollTimersRef.current.delete(queueItem.projectId);
                setQueue((prev) =>
                  prev.map((item) =>
                    item.projectId === queueItem.projectId
                      ? { ...item, status: 'failed' as const, progress: 0, error: 'Render failed' }
                      : item
                  )
                );
                resolve();
                return;
              }

              // Update progress
              setQueue((prev) =>
                prev.map((item) =>
                  item.projectId === queueItem.projectId
                    ? {
                        ...item,
                        progress: status.progress?.percentage ?? item.progress,
                        currentPhase: status.progress?.current_phase ?? item.currentPhase,
                        currentSegment: status.progress?.current_segment ?? item.currentSegment,
                        totalSegments: status.progress?.total_segments ?? item.totalSegments,
                      }
                    : item
                )
              );
            } catch {
              // Transient error — keep polling
            }
          }, POLL_INTERVAL);

          pollTimersRef.current.set(queueItem.projectId, timer);
        });
      } catch (err: unknown) {
        const axiosErr = err as { response?: { status?: number; data?: Record<string, unknown> } };
        const status = axiosErr?.response?.status;

        let errorMsg = 'Failed to start render';
        if (status === 400) {
          const data = axiosErr?.response?.data;
          errorMsg = String(data?.message || data?.error || 'Validation failed on server');
        } else if (status === 409) {
          errorMsg = 'Project is already being rendered';
        }

        setQueue((prev) =>
          prev.map((item) =>
            item.projectId === queueItem.projectId
              ? { ...item, status: 'failed' as const, error: errorMsg, currentPhase: 'Failed' }
              : item
          )
        );
      }
    }

    if (!mountedRef.current) return;
    setIsRunning(false);
    setIsCancelling(false);
    cancelledRef.current = false;
    // Re-run the backend preflight so statuses/readiness reflect the new
    // renderings without forcing the user to press Refresh.
    await fetchAndValidate({ silent: true });
  }, [readyProjects, selectedIds, fetchAndValidate]);

  // ── Cancel bulk render ──
  const handleCancelBulk = useCallback(() => {
    cancelledRef.current = true;
    setIsCancelling(true);
    toast.info('Cancelling bulk render…');
  }, []);

  // ── Clear queue ──
  const clearQueue = useCallback(() => {
    // Clean up any remaining timers
    pollTimersRef.current.forEach((timer) => clearInterval(timer));
    pollTimersRef.current.clear();
    setQueue([]);
    setIsRunning(false);
    setIsCancelling(false);
    cancelledRef.current = false;
  }, []);

  // ── Queue summary ──
  const queueSummary = useMemo(() => {
    const completed = queue.filter((q) => q.status === 'completed').length;
    const failed = queue.filter((q) => q.status === 'failed').length;
    const cancelled = queue.filter((q) => q.status === 'cancelled').length;
    const rendering = queue.filter((q) => q.status === 'rendering').length;
    const queued = queue.filter((q) => q.status === 'queued').length;
    return { completed, failed, cancelled, rendering, queued, total: queue.length };
  }, [queue]);

  // ── Render ──
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bulk Create</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Select ready projects and render them in batch
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void fetchAndValidate()} disabled={loading || isRunning}>
          <RefreshCw className={`size-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="size-4" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Project Selection Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="size-5 text-muted-foreground" />
              <h2 className="font-semibold">Projects</h2>
              {!loading && (
                <span className="text-muted-foreground text-sm">
                  ({readyProjects.length} ready of {projectItems.length})
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {readyProjects.length > 0 && !isRunning && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={toggleSelectAll}
                  className="text-xs"
                >
                  {allReadySelected ? 'Deselect all' : 'Select all ready'}
                </Button>
              )}
              {selectedReadyCount > 0 && !isRunning && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button size="sm">
                      <Play className="size-4 mr-2" />
                      Render {selectedReadyCount} project{selectedReadyCount !== 1 ? 's' : ''}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Start Bulk Render</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will render {selectedReadyCount} project{selectedReadyCount !== 1 ? 's' : ''} sequentially.
                        Each project will go through the full render pipeline. This may take a while depending on the number of segments.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={startBulkRender}>
                        Start Rendering
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-4">
                  <Skeleton className="size-4 rounded" />
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="h-4 w-20 ml-auto" />
                </div>
              ))}
            </div>
          ) : projectItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Layers className="size-10 mb-3 opacity-50" />
              <p className="font-medium">No projects found</p>
              <p className="text-sm mt-1">Create a project first, then come back here</p>
              <Button asChild variant="outline" size="sm" className="mt-4">
                <Link href={withAccount(`/${section}/projects`, accountId)}>Go to Projects</Link>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    {readyProjects.length > 0 && !isRunning && (
                      <Checkbox
                        checked={allReadySelected}
                        onCheckedChange={toggleSelectAll}
                        aria-label="Select all ready projects"
                      />
                    )}
                  </TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Segments</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Readiness</TableHead>
                  <TableHead className="text-right">Issues</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projectItems.map((item) => {
                  const isReady = item.readiness === 'ready';
                  const isChecked = selectedIds.has(item.id);
                  const readinessBadge = getReadinessBadge(item);
                  const statusBadge = deriveProjectBadge(item.status);
                  const issueText = getIssueTooltip(item);

                  return (
                    <TableRow
                      key={item.id}
                      className={isReady ? 'cursor-pointer' : 'opacity-60'}
                      onClick={() => isReady && !isRunning && toggleSelect(item.id)}
                    >
                      <TableCell onClick={(event) => event.stopPropagation()}>
                        <Checkbox
                          checked={isChecked}
                          onCheckedChange={() => toggleSelect(item.id)}
                          disabled={!isReady || isRunning}
                          aria-label={`Select ${item.title}`}
                        />
                      </TableCell>
                      <TableCell className="font-medium max-w-75 truncate">
                        <Link
                          href={projectHref(item.id)}
                          className="hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {item.title}
                        </Link>
                      </TableCell>
                      <TableCell>{item.segmentCount}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={statusBadge.className}>
                          {statusBadge.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={readinessBadge.className}>
                          {item.readiness === 'checking' && (
                            <Loader2 className="size-3 mr-1 animate-spin" />
                          )}
                          {readinessBadge.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {item.readiness === 'not-ready' && issueText && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                                {item.emptySegments && (
                                  <span className="text-xs">No segments</span>
                                )}
                                {item.missingImages > 0 && (
                                  <span className="inline-flex items-center gap-0.5 text-xs">
                                    <ImageOff className="size-3" />
                                    {item.missingImages}
                                  </span>
                                )}
                                {item.missingAudio > 0 && (
                                  <span className="inline-flex items-center gap-0.5 text-xs">
                                    <Volume2 className="size-3" />
                                    {item.missingAudio}
                                  </span>
                                )}
                              </div>
                            </TooltipTrigger>
                            <TooltipContent side="left">
                              <p className="whitespace-pre-line text-xs">{issueText}</p>
                            </TooltipContent>
                          </Tooltip>
                        )}
                        {item.readiness === 'processing' && (
                          <span className="text-xs text-muted-foreground">Already rendering</span>
                        )}
                        {item.readiness === 'ready' && (
                          <CheckCircle2 className="size-4 text-green-500 inline" />
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Render Queue */}
      {queue.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Play className="size-5 text-muted-foreground" />
                <h2 className="font-semibold">Render Queue</h2>
                <span className="text-muted-foreground text-sm">
                  ({queueSummary.completed}/{queueSummary.total} completed
                  {queueSummary.failed > 0 && `, ${queueSummary.failed} failed`}
                  {queueSummary.cancelled > 0 && `, ${queueSummary.cancelled} cancelled`})
                </span>
              </div>
              <div className="flex items-center gap-2">
                {isRunning && !isCancelling && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" size="sm">
                        <Square className="size-4 mr-2" />
                        Cancel All
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Cancel Bulk Render</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will cancel the currently rendering project and skip all remaining queued projects.
                          Projects that already completed will keep their rendered output.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Keep Rendering</AlertDialogCancel>
                        <AlertDialogAction onClick={handleCancelBulk}>
                          Cancel All
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                )}
                {isRunning && isCancelling && (
                  <Button variant="outline" size="sm" disabled>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    Cancelling…
                  </Button>
                )}
                {queueCompleted && (
                  <Button variant="outline" size="sm" onClick={clearQueue}>
                    <XCircle className="size-4 mr-2" />
                    Clear Queue
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {queue.map((item) => {
                const badge = getQueueStatusBadge(item.status);
                return (
                  <div key={item.projectId} className="px-6 py-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        {item.status === 'rendering' && (
                          <Loader2 className="size-4 animate-spin text-blue-500" />
                        )}
                        {item.status === 'completed' && (
                          <CheckCircle2 className="size-4 text-green-500" />
                        )}
                        {item.status === 'failed' && (
                          <AlertCircle className="size-4 text-destructive" />
                        )}
                        {item.status === 'queued' && (
                          <Clock className="size-4 text-muted-foreground" />
                        )}
                        {item.status === 'cancelled' && (
                          <XCircle className="size-4 text-muted-foreground" />
                        )}
                        <Link
                          href={projectHref(item.projectId)}
                          className="font-medium hover:underline"
                        >
                          {item.title}
                        </Link>
                        <Badge variant="outline" className={badge.className}>
                          {badge.label}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {item.status === 'rendering' && (
                          <span>
                            {item.currentPhase} — Segment {item.currentSegment}/{item.totalSegments} ({item.progress}%)
                          </span>
                        )}
                        {item.status === 'completed' && <span>100%</span>}
                        {item.status === 'failed' && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-destructive cursor-help">
                                <Info className="size-3 inline mr-1" />
                                Error
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-xs">{item.error || 'Unknown error'}</p>
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    </div>
                    {(item.status === 'rendering' || item.status === 'completed') && (
                      <Progress value={item.progress} className="h-2" />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Info note */}
      {!isRunning && queue.length === 0 && (
        <div className="flex items-start gap-3 rounded-lg border p-4 text-sm text-muted-foreground">
          <Info className="size-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-foreground">How Bulk Create works</p>
            <ul className="mt-1 space-y-1 list-disc list-inside">
              <li>Only projects with <strong>all segments having images and audio</strong> can be selected</li>
              <li>Projects are rendered <strong>sequentially</strong> (one at a time) to avoid overloading the server</li>
              <li>You can cancel the batch at any time — completed renders are preserved</li>
              <li>Projects currently being rendered elsewhere are excluded from selection</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Project status badge (reused from projects page) ──

function deriveProjectBadge(status: Project['status']) {
  switch (status) {
    case 'COMPLETED':
      return { label: 'Rendered', className: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30' };
    case 'FAILED':
      return { label: 'Error', className: 'bg-destructive/15 text-destructive border-destructive/30' };
    case 'PROCESSING':
      return { label: 'Rendering', className: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30' };
    default:
      return { label: 'Draft', className: 'bg-muted text-muted-foreground border-muted' };
  }
}
