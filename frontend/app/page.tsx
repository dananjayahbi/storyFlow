'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { getProjects } from '@/lib/api';
import { Project } from '@/lib/types';
import { ProjectCard } from '@/components/ProjectCard';
import { CreateProjectDialog } from '@/components/CreateProjectDialog';
import ImportDialog from '@/components/ImportDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/EmptyState';
import { FolderPlus, Search, X, ArrowUpDown, Settings } from 'lucide-react';
import { toast } from 'sonner';

// ── Sort modes (Step 2) ──

type SortMode = 'date-desc' | 'date-asc' | 'title-asc' | 'title-desc';

const SORT_LABELS: Record<SortMode, string> = {
  'date-desc': 'Newest first',
  'date-asc': 'Oldest first',
  'title-asc': 'Title A–Z',
  'title-desc': 'Title Z–A',
};

const SORT_CYCLE: SortMode[] = ['date-desc', 'date-asc', 'title-asc', 'title-desc'];

// ── Skeleton card (Step 4) ──

function SkeletonCard() {
  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Thumbnail placeholder */}
      <div className="aspect-video bg-muted animate-pulse" />
      <div className="p-4 space-y-3">
        <div className="h-5 w-3/4 bg-muted animate-pulse rounded" />
        <div className="h-4 w-1/3 bg-muted animate-pulse rounded" />
        <div className="flex items-center justify-between pt-2">
          <div className="h-3 w-1/2 bg-muted animate-pulse rounded" />
          <div className="h-5 w-14 bg-muted animate-pulse rounded-full" />
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showImportDialog, setShowImportDialog] = useState(false);

  // Sort & search state
  const [sortMode, setSortMode] = useState<SortMode>('date-desc');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getProjects();
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
  }, []);

  const handleProjectCreated = () => {
    fetchProjects();
  };

  const handleProjectDelete = (id: string) => {
    setProjects((prev) => prev.filter((p) => String(p.id) !== id));
    toast('Project deleted', {
      description: 'Project and all media removed.',
    });
  };

  // Cycle through sort modes
  const handleSortCycle = () => {
    setSortMode((prev) => {
      const idx = SORT_CYCLE.indexOf(prev);
      return SORT_CYCLE[(idx + 1) % SORT_CYCLE.length];
    });
  };

  // Filter and sort (Steps 2 & 3)
  const filteredProjects = useMemo(() => {
    let list = [...projects];

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
  }, [projects, sortMode, searchQuery]);

  if (error) {
    return (
      <div>
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-3xl font-bold">Projects</h2>
        </div>
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-3xl font-bold">Projects</h2>
        <div className="flex gap-2">
          <CreateProjectDialog onProjectCreated={handleProjectCreated} />
          <Button variant="outline" onClick={() => setShowImportDialog(true)}>
            Import Story
          </Button>
          <Button variant="outline" asChild>
            <Link href="/settings">
              <Settings className="h-4 w-4 mr-1" />
              Settings
            </Link>
          </Button>
        </div>
      </div>

      <ImportDialog
        open={showImportDialog}
        onOpenChange={setShowImportDialog}
        onSuccess={(project) => {
          router.push(`/projects/${project.id}`);
        }}
      />

      {/* Sort & Search Controls (Steps 2 & 3) */}
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
        </div>
      )}

      {/* Loading Skeletons (Step 4) */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
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
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProjects.map((project) => (
            <ProjectCard key={project.id} project={project} onDelete={handleProjectDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
