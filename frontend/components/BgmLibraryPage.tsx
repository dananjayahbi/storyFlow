'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import {
  Disc3,
  Loader2,
  Music,
  Pencil,
  RefreshCw,
  Search,
  Share2,
  Trash2,
  Upload,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  deleteBgmClip,
  getBgmClips,
  updateBgmClip,
  uploadBgmClip,
} from '@/lib/api';
import type { BgmClip } from '@/lib/types';
import { sectionFromPathname } from '@/lib/section';
import { useAccountId } from '@/lib/useAccountId';
import { AudioPlayer } from '@/components/AudioPlayer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { formatTime } from '@/lib/utils';

const ACCEPTED_AUDIO =
  '.mp3,.wav,.flac,.m4a,.aac,.ogg,.oga,.opus,.wma,.aiff,.aif,.alac,.webm,audio/*';

function humanSize(bytes: number): string {
  if (!bytes) return '—';
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function errorMessage(err: unknown): string {
  const axiosErr = err as {
    response?: { data?: { error?: string; details?: string } };
    message?: string;
  };
  const data = axiosErr?.response?.data;
  return data?.details || data?.error || axiosErr?.message || 'Something went wrong.';
}

export function BgmLibraryPage() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);
  const accountId = useAccountId(section);

  const [clips, setClips] = useState<BgmClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [isShared, setIsShared] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const [renaming, setRenaming] = useState<BgmClip | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [savingRename, setSavingRename] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const fetchClips = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setClips(await getBgmClips());
    } catch {
      setError('Failed to load the BGM Library. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!accountId) return;
    void fetchClips();
  }, [accountId, fetchClips, section]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return clips;
    return clips.filter(
      (clip) =>
        clip.name.toLowerCase().includes(needle) ||
        clip.original_name.toLowerCase().includes(needle) ||
        (clip.account_name || '').toLowerCase().includes(needle)
    );
  }, [clips, query]);

  const handleUpload = async () => {
    if (!file) {
      toast.error('Choose an audio file first.');
      return;
    }
    setUploading(true);
    try {
      const clip = await uploadBgmClip(file, {
        name: name.trim() || undefined,
        isShared,
      });
      setClips((prev) => [clip, ...prev]);
      setFile(null);
      setName('');
      setIsShared(false);
      if (inputRef.current) inputRef.current.value = '';
      toast.success(`Added “${clip.name}” to the BGM Library`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const handleShareToggle = async (clip: BgmClip) => {
    if (!clip.can_edit || busyId) return;
    setBusyId(clip.id);
    try {
      const updated = await updateBgmClip(clip.id, {
        is_shared: !clip.is_shared,
      });
      setClips((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item))
      );
      toast.success(
        updated.is_shared
          ? `“${updated.name}” is now shared with this domain`
          : `“${updated.name}” is private to this account again`
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleRename = async () => {
    if (!renaming) return;
    const next = renameValue.trim();
    if (!next) {
      toast.error('A track name is required.');
      return;
    }
    setSavingRename(true);
    try {
      const updated = await updateBgmClip(renaming.id, { name: next });
      setClips((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item))
      );
      setRenaming(null);
      toast.success('Track renamed');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSavingRename(false);
    }
  };

  const handleDelete = async (clip: BgmClip) => {
    setBusyId(clip.id);
    try {
      await deleteBgmClip(clip.id);
      setClips((prev) => prev.filter((item) => item.id !== clip.id));
      toast.success(`Deleted “${clip.name}”`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  if (!accountId) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading the music library…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Music className="h-6 w-6 text-primary" />
            BGM Library
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Background music for this account. Tracks marked shared are also
            visible to every account in the same domain.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void fetchClips()} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Upload */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Upload className="h-4 w-4 text-primary" />
            Upload background music
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto] md:items-start">
            <div className="space-y-2">
              <label htmlFor="bgm-file" className="text-sm font-medium">
                Audio file
              </label>
              <input
                id="bgm-file"
                ref={inputRef}
                type="file"
                accept={ACCEPTED_AUDIO}
                onChange={(event) => {
                  const selected = event.target.files?.[0] ?? null;
                  setFile(selected);
                  if (selected && !name) {
                    setName(selected.name.replace(/\.[^.]+$/, ''));
                  }
                }}
                className="flex h-9 w-full cursor-pointer rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm file:mr-3 file:rounded file:border-0 file:bg-primary/10 file:px-2 file:py-1 file:text-xs file:font-medium file:text-primary"
              />
              <p className="text-xs text-muted-foreground">
                MP3, WAV, FLAC, M4A, OGG, OPUS, WMA, AIFF and more. Every upload
                is converted to MP3 automatically.
              </p>
            </div>

            <div className="space-y-2">
              <label htmlFor="bgm-name" className="text-sm font-medium">
                Track name
              </label>
              <Input
                id="bgm-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Slow ocean drone"
              />
            </div>

            <div className="space-y-2 md:min-w-[180px]">
              <label htmlFor="bgm-shared" className="text-sm font-medium">
                Sharing
              </label>
              <div className="flex h-9 items-center gap-2 whitespace-nowrap">
                <input
                  id="bgm-shared"
                  type="checkbox"
                  checked={isShared}
                  onChange={(event) => setIsShared(event.target.checked)}
                  className="h-4 w-4 shrink-0 accent-primary"
                />
                <label htmlFor="bgm-shared" className="text-sm">
                  Share with this domain
                </label>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void handleUpload()} disabled={uploading || !file}>
              {uploading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              {uploading ? 'Converting…' : 'Upload & convert'}
            </Button>
            {file && (
              <span className="text-xs text-muted-foreground">
                {file.name} · {humanSize(file.size)}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search tracks or accounts…"
          className="pl-9"
        />
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : clips.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
              <Disc3 className="h-7 w-7 text-primary" />
            </div>
            <p className="text-lg font-semibold">No background music yet</p>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Upload your first track above. It will be converted to MP3 and
              stored for this account.
            </p>
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          No tracks match “{query}”.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((clip) => (
            <Card key={clip.id} className="flex h-full flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="line-clamp-2 min-h-[2.75rem] min-w-0 text-base leading-snug">
                    {clip.name}
                  </CardTitle>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <Badge variant="secondary">MP3</Badge>
                    {clip.is_shared && (
                      <Badge variant="outline" className="gap-1 text-primary">
                        <Users className="h-3 w-3" />
                        Shared
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex min-h-5 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>{formatTime(clip.duration || 0)}</span>
                  <span>{humanSize(clip.file_size)}</span>
                  {clip.original_format && (
                    <span>from {clip.original_format.toUpperCase()}</span>
                  )}
                  {clip.is_shared && clip.account_name && (
                    <span className="inline-flex items-center gap-1">
                      <Share2 className="h-3 w-3" />
                      {clip.account_name}
                    </span>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col justify-between gap-4">
                {clip.file_url ? (
                  <AudioPlayer audioUrl={clip.file_url} duration={clip.duration || 0} />
                ) : (
                  <p className="text-xs text-muted-foreground">Audio unavailable</p>
                )}

                <div className="mt-auto flex items-center gap-2">
                  {clip.can_edit ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-9 min-w-0 flex-1"
                        onClick={() => void handleShareToggle(clip)}
                        disabled={busyId === clip.id}
                      >
                        <Share2 className="mr-2 h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">
                          {clip.is_shared ? 'Make private' : 'Share'}
                        </span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 shrink-0"
                        title="Rename"
                        onClick={() => {
                          setRenaming(clip);
                          setRenameValue(clip.name);
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 shrink-0 text-destructive hover:text-destructive"
                            disabled={busyId === clip.id}
                          >
                            {busyId === clip.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Delete “{clip.name}”?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              This removes the MP3 from this account&apos;s BGM
                              Library. It cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              onClick={() => void handleDelete(clip)}
                            >
                              Delete track
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Shared by {clip.account_name}. Only the owner can edit it.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!renaming} onOpenChange={(open) => !open && setRenaming(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename track</DialogTitle>
            <DialogDescription>
              The file itself is unchanged; only the display name is updated.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
            placeholder="Track name"
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void handleRename();
              }
            }}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenaming(null)}>
              Cancel
            </Button>
            <Button onClick={() => void handleRename()} disabled={savingRename}>
              {savingRename && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save name
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
