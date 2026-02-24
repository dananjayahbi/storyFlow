'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { getProjects } from '@/lib/api';
import { Project } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  FolderOpen,
  Film,
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { DashboardSkeleton } from '@/components/skeletons';

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

// ── Status badge ──

function deriveBadge(status: Project['status']) {
  switch (status) {
    case 'COMPLETED':
      return { label: 'Rendered', className: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30' };
    case 'FAILED':
      return { label: 'Error', className: 'bg-destructive/15 text-destructive border-destructive/30' };
    case 'PROCESSING':
      return { label: 'In Progress', className: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30' };
    default:
      return { label: 'Draft', className: 'bg-muted text-muted-foreground border-border' };
  }
}

// ── Stat card component ──

interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: React.ElementType;
  iconClassName?: string;
}

function StatCard({ title, value, description, icon: Icon, iconClassName }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <Icon className={`h-4 w-4 text-muted-foreground ${iconClassName ?? ''}`} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Skeleton stat card (kept for reference; route-level loading.tsx now provides DashboardSkeleton) ──

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const data = await getProjects();
        setProjects(data.results);
      } catch (err) {
        setError('Failed to load dashboard data.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ── Computed stats ──

  const stats = useMemo(() => {
    const total = projects.length;
    const drafts = projects.filter((p) => p.status === 'DRAFT').length;
    const rendered = projects.filter((p) => p.status === 'COMPLETED').length;
    const failed = projects.filter((p) => p.status === 'FAILED').length;
    const processing = projects.filter((p) => p.status === 'PROCESSING').length;
    const totalSegments = projects.reduce((sum, p) => sum + (p.segment_count || 0), 0);

    return { total, drafts, rendered, failed, processing, totalSegments };
  }, [projects]);

  const recentProjects = useMemo(() => {
    return [...projects]
      .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
      .slice(0, 5);
  }, [projects]);

  if (error) {
    return (
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-4">Dashboard</h2>
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Overview of your StoryFlow workspace
          </p>
        </div>
        <Button asChild size="sm" variant="outline">
          <Link href="/projects">
            View All Projects
            <ArrowRight className="ml-2 h-3.5 w-3.5" />
          </Link>
        </Button>
      </div>

      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        <StatCard
          title="Total Projects"
          value={stats.total}
          description={`${stats.totalSegments} total segments`}
          icon={FolderOpen}
        />
        <StatCard
          title="Drafts"
          value={stats.drafts}
          description="Awaiting content"
          icon={FileText}
        />
        <StatCard
          title="Rendered"
          value={stats.rendered}
          description="Ready to watch"
          icon={CheckCircle2}
          iconClassName="text-green-500"
        />
        <StatCard
          title="In Progress"
          value={stats.processing}
          description="Currently rendering"
          icon={Loader2}
          iconClassName="text-amber-500"
        />
        <StatCard
          title="Failed"
          value={stats.failed}
          description="Need attention"
          icon={AlertCircle}
          iconClassName="text-destructive"
        />
      </div>

      {/* ── Recent Projects ── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold tracking-tight">Recent Activity</h3>
        </div>

        {recentProjects.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Film className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">No projects yet. Create one to get started!</p>
            <Button asChild size="sm" className="mt-4">
              <Link href="/projects">Go to Projects</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {recentProjects.map((project) => {
              const badge = deriveBadge(project.status);
              return (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="flex items-center gap-4 rounded-lg border p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-muted shrink-0">
                    <Film className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{project.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {project.segment_count} segment{project.segment_count !== 1 ? 's' : ''} ·{' '}
                      <Clock className="inline h-3 w-3 -mt-0.5" />{' '}
                      {formatRelativeTime(project.updated_at || project.created_at)}
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className={`text-[11px] px-2 py-0.5 shrink-0 ${badge.className}`}
                  >
                    {badge.label}
                  </Badge>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
