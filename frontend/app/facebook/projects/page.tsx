'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import {
  getProjects,
  getSettings,
  updateSettings,
  deleteProject,
  updateProject,
  uploadProjectThumbnail,
  removeProjectThumbnail,
} from '@/lib/api';
import { Project } from '@/lib/types';
import { sectionFromPathname } from '@/lib/section';
import { CreateProjectDialog } from '@/components/CreateProjectDialog';
import ImportDialog from '@/components/ImportDialog';
import { ProjectTile } from '@/components/ProjectTile';
import { ProjectThumbnail } from '@/components/ProjectThumbnail';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { EmptyState } from '@/components/EmptyState';
import { StoryTemplateModal } from '@/components/StoryTemplateModal';
import {
  FolderPlus,
  Search,
  X,
  ArrowUpDown,
  Trash2,
  Pencil,
  LayoutGrid,
  Rows3,
} from 'lucide-react';
import { toast } from 'sonner';
import { ProjectsSkeleton } from '@/components/skeletons';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog';

// ── Sort modes ──

type SortMode = 'date-desc' | 'date-asc' | 'title-asc' | 'title-desc';

const SORT_LABELS: Record<SortMode, string> = {
  'date-desc': 'Newest first',
  'date-asc': 'Oldest first',
  'title-asc': 'Title A–Z',
  'title-desc': 'Title Z–A',
};

const SORT_CYCLE: SortMode[] = ['date-desc', 'date-asc', 'title-asc', 'title-desc'];

// ── Skeleton row (kept for reference; ProjectsSkeleton now used for full-page loading) ──

// ── Relative time utility ──

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
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ── Status badge logic ──

type DerivedStatus = 'Draft' | 'In Progress' | 'Rendered' | 'Error';

function deriveBadge(status: Project['status']): {
  label: DerivedStatus;
  className: string;
} {
  switch (status) {
    case 'COMPLETED':
      return { label: 'Rendered', className: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30' };
    case 'FAILED':
      return { label: 'Error', className: 'bg-destructive/15 text-destructive border-destructive/30' };
    case 'PROCESSING':
      return { label: 'In Progress', className: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30 animate-pulse' };
    default:
      return { label: 'Draft', className: 'bg-muted text-muted-foreground border-border' };
  }
}

export default function ProjectsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const activeSection = sectionFromPathname(pathname);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showImportDialog, setShowImportDialog] = useState(false);

  // Sort & search state
  const [sortMode, setSortMode] = useState<SortMode>('date-desc');
  const [searchQuery, setSearchQuery] = useState('');

  // Layout preference (persisted per account in AccountSettings).
  const [viewMode, setViewMode] = useState<'table' | 'tiles'>('table');

  // One shared delete confirmation for both layouts.
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [thumbnailBusyId, setThumbnailBusyId] = useState<string | null>(null);

  // Rename state
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renamingProject, setRenamingProject] = useState<Project | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameLoading, setRenameLoading] = useState(false);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getProjects(activeSection);
      setProjects(data.results);
    } catch (err) {
      setError('Failed to load projects. Is the backend server running?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [activeSection]);

  // Load the saved layout for this account. Failures keep the table default.
  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then((settings) => {
        if (cancelled) return;
        if (
          settings.projects_view_mode === 'table' ||
          settings.projects_view_mode === 'tiles'
        ) {
          setViewMode(settings.projects_view_mode);
        }
      })
      .catch(() => {
        /* not fatal — keep the table view */
      });
    return () => {
      cancelled = true;
    };
  }, [activeSection]);

  const handleViewModeChange = async (mode: 'table' | 'tiles') => {
    if (mode === viewMode) return;
    const previous = viewMode;
    setViewMode(mode);
    try {
      await updateSettings({ projects_view_mode: mode });
    } catch {
      setViewMode(previous);
      toast.error('Could not save the projects layout.');
    }
  };

  const applyThumbnailUpdate = (
    projectId: string,
    updated: Partial<Project>,
  ) => {
    setProjects((previous) =>
      previous.map((project) =>
        String(project.id) === projectId
          ? {
              ...project,
              thumbnail_url: updated.thumbnail_url ?? null,
              manual_thumbnail_url: updated.manual_thumbnail_url ?? null,
              has_manual_thumbnail: updated.has_manual_thumbnail ?? false,
              thumbnail_source: updated.thumbnail_source ?? null,
            }
          : project,
      ),
    );
  };

  const handleThumbnailUpload = async (project: Project, file: File) => {
    const projectId = String(project.id);
    setThumbnailBusyId(projectId);
    try {
      const updated = await uploadProjectThumbnail(projectId, file);
      applyThumbnailUpdate(projectId, updated);
      toast('Project thumbnail updated');
    } catch {
      toast.error('Could not upload that image. Try a JPG or PNG.');
    } finally {
      setThumbnailBusyId(null);
    }
  };

  const handleThumbnailRemove = async (project: Project) => {
    const projectId = String(project.id);
    setThumbnailBusyId(projectId);
    try {
      const updated = await removeProjectThumbnail(projectId);
      applyThumbnailUpdate(projectId, updated);
      toast('Manual thumbnail removed');
    } catch {
      toast.error('Could not remove the manual thumbnail.');
    } finally {
      setThumbnailBusyId(null);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    const projectId = String(deleteTarget.id);
    try {
      await deleteProject(projectId);
      handleProjectDelete(projectId);
    } catch {
      toast.error('Could not delete that project.');
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleProjectCreated = () => {
    fetchProjects();
  };

  const handleProjectDelete = (id: string) => {
    setProjects((prev) => prev.filter((p) => String(p.id) !== id));
    toast('Project deleted', {
      description: 'Project and all media removed.',
    });
  };

  const openRenameDialog = (project: Project) => {
    setRenamingProject(project);
    setRenameValue(project.title);
    setRenameDialogOpen(true);
  };

  const handleRename = async () => {
    if (!renamingProject || !renameValue.trim()) return;
    if (renameValue.trim() === renamingProject.title) {
      setRenameDialogOpen(false);
      return;
    }
    setRenameLoading(true);
    try {
      const updated = await updateProject(String(renamingProject.id), { title: renameValue.trim() });
      setProjects((prev) =>
        prev.map((p) => (String(p.id) === String(renamingProject.id) ? { ...p, title: updated.title } : p))
      );
      toast('Project renamed', { description: `Renamed to "${updated.title}".` });
      setRenameDialogOpen(false);
    } catch {
      toast.error('Failed to rename project');
    } finally {
      setRenameLoading(false);
    }
  };

  // Cycle through sort modes
  const handleSortCycle = () => {
    setSortMode((prev) => {
      const idx = SORT_CYCLE.indexOf(prev);
      return SORT_CYCLE[(idx + 1) % SORT_CYCLE.length];
    });
  };

  // Filter and sort
  const filteredProjects = useMemo(() => {
    let list = [...projects];

    // Keep Facebook and YouTube data fully separated
    list = list.filter((p) => (p.section || 'facebook') === activeSection);

    // Case-insensitive title search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((p) => p.title.toLowerCase().includes(q));
    }

    // Sort
    list.sort((a, b) => {
      switch (sortMode) {
        case 'date-desc':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'date-asc':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case 'title-asc':
          return a.title.localeCompare(b.title);
        case 'title-desc':
          return b.title.localeCompare(a.title);
        default:
          return 0;
      }
    });

    return list;
  }, [projects, sortMode, searchQuery, activeSection]);

  if (error) {
    return (
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold tracking-tight">Projects</h2>
        </div>
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Projects</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your narrative video projects
          </p>
        </div>
        <div className="flex gap-2">
          <StoryTemplateModal />
          <CreateProjectDialog onProjectCreated={handleProjectCreated} />
          <Button variant="outline" size="sm" onClick={() => setShowImportDialog(true)}>
            Import Story
          </Button>
        </div>
      </div>

      <ImportDialog
        open={showImportDialog}
        onOpenChange={setShowImportDialog}
        onSuccess={(project) => {
          router.push(`/${activeSection}/projects/${project.id}`);
        }}
      />

      {/* Sort & Search Controls */}
      {!loading && projects.length > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-6">
          {/* Search bar */}
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-8"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded-sm hover:bg-muted transition-colors"
                aria-label="Clear search"
              >
                <X className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            )}
          </div>

          {/* Sort toggle */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleSortCycle}
            className="gap-1.5 whitespace-nowrap"
          >
            <ArrowUpDown className="h-3.5 w-3.5" />
            {SORT_LABELS[sortMode]}
          </Button>

          {/* Layout toggle — saved to the account settings */}
          <div
            className="inline-flex items-center gap-0.5 rounded-md border p-0.5"
            role="group"
            aria-label="Projects layout"
          >
            <Button
              variant={viewMode === 'table' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 gap-1 px-2 text-xs"
              aria-pressed={viewMode === 'table'}
              onClick={() => void handleViewModeChange('table')}
              title="Table view"
            >
              <Rows3 className="h-3.5 w-3.5" />
              Table
            </Button>
            <Button
              variant={viewMode === 'tiles' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 gap-1 px-2 text-xs"
              aria-pressed={viewMode === 'tiles'}
              onClick={() => void handleViewModeChange('tiles')}
              title="Tile view"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Tiles
            </Button>
          </div>
        </div>
      )}

      {/* Loading Skeletons */}
      {loading ? (
        <ProjectsSkeleton />
      ) : projects.length === 0 ? (
        <EmptyState
          icon={FolderPlus}
          title="No projects yet"
          description="Create your first story to get started!"
          actionLabel="+ New Project"
          onAction={() => {
            const trigger = document.querySelector<HTMLButtonElement>('[data-create-project-trigger]');
            trigger?.click();
          }}
        />
      ) : filteredProjects.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No matching projects"
          description={`No projects match "${searchQuery}". Try a different search term.`}
          actionLabel="Clear search"
          onAction={() => setSearchQuery('')}
        />
      ) : viewMode === 'tiles' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredProjects.map((project) => {
            const badge = deriveBadge(project.status);
            const updatedAt = project.updated_at || project.created_at;
            const projectId = String(project.id);
            return (
              <ProjectTile
                key={project.id}
                project={project}
                badge={badge}
                updatedLabel={formatRelativeTime(updatedAt)}
                updatedAbsolute={formatAbsoluteDate(updatedAt)}
                thumbnailBusy={thumbnailBusyId === projectId}
                onOpen={() =>
                  router.push(`/${activeSection}/projects/${project.id}`)
                }
                onRename={() => openRenameDialog(project)}
                onRequestDelete={() => setDeleteTarget(project)}
                onThumbnailUpload={(file) =>
                  void handleThumbnailUpload(project, file)
                }
                onThumbnailRemove={() =>
                  void handleThumbnailRemove(project)
                }
              />
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">Preview</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Segments</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="w-20"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProjects.map((project) => {
                const badge = deriveBadge(project.status);
                const projectId = String(project.id);
                return (
                  <TableRow
                    key={project.id}
                    className="cursor-pointer"
                    onClick={() =>
                      router.push(`/${activeSection}/projects/${project.id}`)
                    }
                  >
                    <TableCell className="py-2">
                      <ProjectThumbnail
                        project={project}
                        className="h-12 w-20 rounded-md border"
                        compact
                        editable
                        busy={thumbnailBusyId === projectId}
                        onUpload={(file) =>
                          void handleThumbnailUpload(project, file)
                        }
                        onRemove={() => void handleThumbnailRemove(project)}
                      />
                    </TableCell>
                    <TableCell
                      className="max-w-75 truncate font-medium"
                      title={project.title}
                    >
                      {project.title}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={`text-[11px] px-2 py-0.5 ${badge.className}`}
                      >
                        {badge.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {project.segment_count}
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="text-xs text-muted-foreground cursor-default">
                            {formatRelativeTime(project.updated_at || project.created_at)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom">
                          <p className="text-xs">{formatAbsoluteDate(project.updated_at || project.created_at)}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-muted-foreground hover:text-foreground"
                              onClick={() => openRenameDialog(project)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom"><p className="text-xs">Rename</p></TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => setDeleteTarget(project)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom"><p className="text-xs">Delete</p></TooltipContent>
                        </Tooltip>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Shared delete confirmation (table and tile views) */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Project</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{deleteTarget?.title}&quot;?
              All segments and associated media will be permanently removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void handleConfirmDelete()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rename Project</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              placeholder="Project title"
              onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" size="sm">Cancel</Button>
            </DialogClose>
            <Button
              size="sm"
              onClick={handleRename}
              disabled={renameLoading || !renameValue.trim()}
            >
              {renameLoading ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
