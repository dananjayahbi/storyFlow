'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getProjects } from '@/lib/api';
import { Project } from '@/lib/types';
import { ProjectCard } from '@/components/ProjectCard';
import { CreateProjectDialog } from '@/components/CreateProjectDialog';
import ImportDialog from '@/components/ImportDialog';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';
import { FolderPlus } from 'lucide-react';
import { toast } from 'sonner';

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showImportDialog, setShowImportDialog] = useState(false);

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

  if (loading) {
    return <p className="text-muted-foreground">Loading projects...</p>;
  }

  if (error) {
    return <p className="text-destructive">{error}</p>;
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
        </div>
      </div>

      <ImportDialog
        open={showImportDialog}
        onOpenChange={setShowImportDialog}
        onSuccess={(project) => {
          router.push(`/projects/${project.id}`);
        }}
      />

      {projects.length === 0 ? (
        <EmptyState
          icon={FolderPlus}
          title="No projects yet"
          description="Create your first story to get started!"
          actionLabel="+ New Project"
          onAction={() => {
            // Trigger CreateProjectDialog by clicking its trigger button
            const trigger = document.querySelector<HTMLButtonElement>('[data-create-project-trigger]');
            trigger?.click();
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} onDelete={handleProjectDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
