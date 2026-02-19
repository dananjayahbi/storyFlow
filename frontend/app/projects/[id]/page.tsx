'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getProject } from '@/lib/api';
import { ProjectDetail } from '@/lib/types';
import { Button } from '@/components/ui/button';

export default function TimelinePage() {
  const params = useParams();
  const id = params.id as string;
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProject = async () => {
      try {
        setLoading(true);
        const data = await getProject(id);
        setProject(data);
      } catch (err) {
        setError('Failed to load project.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchProject();
  }, [id]);

  if (loading) {
    return <p className="text-muted-foreground">Loading project...</p>;
  }

  if (error || !project) {
    return (
      <div>
        <p className="text-destructive mb-4">{error || 'Project not found.'}</p>
        <Link href="/">
          <Button variant="outline">Back to Dashboard</Button>
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <Link href="/">
          <Button variant="outline" size="sm">← Back to Dashboard</Button>
        </Link>
      </div>
      <h2 className="text-3xl font-bold mb-4">{project.title}</h2>
      <div className="rounded-lg border p-8 text-center">
        <p className="text-xl text-muted-foreground">
          Timeline Editor — Coming in Phase 02
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          This page will contain the segment-by-segment editing interface.
        </p>
      </div>
    </div>
  );
}
