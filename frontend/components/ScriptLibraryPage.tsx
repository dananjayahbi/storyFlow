'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BookMarked,
  Clock,
  Eye,
  FilePlus2,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import { deleteScript, getScripts, importProject } from '@/lib/api';
import type { Script } from '@/lib/types';
import { sectionFromPathname, sectionPath } from '@/lib/section';
import { withAccount } from '@/lib/account';
import { useAccountId } from '@/lib/useAccountId';
import { ScriptViewer } from '@/components/ScriptViewer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function ScriptLibraryPage() {
  const pathname = usePathname();
  const router = useRouter();
  const section = sectionFromPathname(pathname);
  const accountId = useAccountId(section);
  const accountHref = (path: string) =>
    accountId ? withAccount(path, accountId) : path;

  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Script | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [creatingScript, setCreatingScript] = useState<Script | null>(null);
  const [createTitle, setCreateTitle] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const fetchScripts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setScripts(await getScripts());
    } catch {
      setError('Failed to load the Script Library. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScripts();
  }, [fetchScripts]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return scripts;
    return scripts.filter(
      (script) =>
        script.title.toLowerCase().includes(needle) ||
        script.pitch.toLowerCase().includes(needle)
    );
  }, [query, scripts]);

  const handleDelete = async (script: Script) => {
    setDeletingId(script.id);
    try {
      await deleteScript(script.id);
      setScripts((prev) => prev.filter((item) => item.id !== script.id));
      if (selected?.id === script.id) setSelected(null);
      toast.success(`Deleted “${script.title}”`);
    } catch {
      toast.error('Failed to delete the script');
    } finally {
      setDeletingId(null);
    }
  };

  const openCreateDialog = (script: Script) => {
    setCreatingScript(script);
    setCreateTitle(script.title);
  };

  const handleCreateProject = async () => {
    if (!creatingScript) return;
    const segmentList = Array.isArray(creatingScript.content?.segments)
      ? creatingScript.content.segments
          .filter((segment) => segment.text_content?.trim())
          .map((segment) => ({
            text_content: segment.text_content,
            image_prompt: segment.image_prompt || '',
          }))
      : [];
    if (segmentList.length === 0) {
      toast.error('This script has no segments to import.');
      return;
    }

    const title = createTitle.trim() || creatingScript.title;
    setIsCreating(true);
    try {
      const project = await importProject({
        format: 'json',
        title,
        section,
        account: accountId || undefined,
        segments: segmentList,
      });
      toast.success(`Created “${title}”`);
      setCreatingScript(null);
      router.push(accountHref(sectionPath(section, `/projects/${project.id}`)));
    } catch {
      toast.error('Failed to create a project from this script');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <BookMarked className="h-6 w-6 text-primary" />
            Script Library
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Scripts saved from Script Craft for this account.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={accountHref(sectionPath(section, '/script-craft'))}>
              <Wand2 className="mr-2 h-4 w-4" />
              Open Script Craft
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchScripts}
            disabled={loading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search titles or pitches…"
          className="pl-9"
        />
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-4 w-32" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : scripts.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
              <BookMarked className="h-7 w-7 text-primary" />
            </div>
            <p className="text-lg font-semibold">No scripts saved yet</p>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Generate a script in Script Craft and click “Save to Library”.
            </p>
            <Button className="mt-5" asChild>
              <Link href={accountHref(sectionPath(section, '/script-craft'))}>
                <Wand2 className="mr-2 h-4 w-4" />
                Write a script
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          No scripts match “{query}”.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((script) => (
            <Card key={script.id} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-base leading-snug">
                    {script.title}
                  </CardTitle>
                  <Badge variant="secondary" className="shrink-0">
                    {script.segment_count} seg
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(script.updated_at)}
                  </span>
                  {script.model_used && (
                    <span className="inline-flex items-center gap-1">
                      <Sparkles className="h-3 w-3" />
                      {script.model_used}
                    </span>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col justify-between gap-4">
                <p className="line-clamp-3 text-sm text-muted-foreground">
                  {script.pitch || script.content?.segments?.[0]?.text_content || '—'}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    className="flex-1"
                    onClick={() => openCreateDialog(script)}
                  >
                    <FilePlus2 className="mr-2 h-4 w-4" />
                    Create
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => setSelected(script)}
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    View
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        disabled={deletingId === script.id}
                      >
                        {deletingId === script.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>
                          Delete “{script.title}”?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                          This removes the saved script from this account&apos;s
                          library. It cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          onClick={() => handleDelete(script)}
                        >
                          Delete script
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={!!creatingScript}
        onOpenChange={(open) => {
          if (!open) setCreatingScript(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create a project</DialogTitle>
            <DialogDescription>
              Start a new project from “{creatingScript?.title}”. Keep the
              original title or change it first.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="create-project-title" className="text-sm font-medium">
                Project title
              </label>
              <Input
                id="create-project-title"
                value={createTitle}
                onChange={(event) => setCreateTitle(event.target.value)}
                placeholder={creatingScript?.title || 'Project title'}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void handleCreateProject();
                }}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                {creatingScript?.segment_count ?? 0} segment
                {(creatingScript?.segment_count ?? 0) === 1 ? '' : 's'} will be
                imported. The original library script stays untouched.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setCreatingScript(null)}
                disabled={isCreating}
              >
                Cancel
              </Button>
              <Button
                onClick={() => void handleCreateProject()}
                disabled={isCreating || !createTitle.trim()}
              >
                {isCreating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <FilePlus2 className="mr-2 h-4 w-4" />
                )}
                Create Project
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Saved script</DialogTitle>
            <DialogDescription>
              {selected ? formatDate(selected.updated_at) : ''}
              {selected?.model_used ? ` · ${selected.model_used}` : ''}
            </DialogDescription>
          </DialogHeader>
          {selected && <ScriptViewer script={selected.content} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
