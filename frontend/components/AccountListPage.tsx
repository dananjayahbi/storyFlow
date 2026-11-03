'use client';

import { useCallback, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  ArrowRight,
  Film,
  FolderKanban,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  UserRound,
  Video,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  createAccount,
  deleteAccount,
  getAccounts,
  updateAccount,
} from '@/lib/api';
import { Account } from '@/lib/types';
import {
  clearStoredAccount,
  getStoredAccountId,
  setStoredAccount,
  withAccount,
} from '@/lib/account';
import { sectionFromPathname, SECTION_LABELS } from '@/lib/section';
import { checkApiHealth, resetApiBaseUrlDiscovery } from '@/lib/apiConfig';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function AccountListPage() {
  const pathname = usePathname();
  const router = useRouter();
  const section = sectionFromPathname(pathname);

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchAccounts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAccounts(section);
      setAccounts(data.results);
    } catch {
      // Distinguish "backend is down" from "backend answered with an error"
      // and show the exact origin the frontend tried to reach.  The backend
      // may have been started on another local port; checkApiHealth() probes
      // /api/health/ and the axios interceptor will have resolved that
      // origin before this code runs.
      const health = await checkApiHealth();
      if (health.ok) {
        setError(
          `The backend is running at ${health.baseUrl}, but the accounts request failed. Check the server console, then retry.`
        );
      } else {
        setError(
          `Cannot reach the StoryFlow backend at ${health.baseUrl}. Start it with "python manage.py runserver 8765" (or set NEXT_PUBLIC_API_URL), then retry.`
        );
      }
    } finally {
      setLoading(false);
    }
  }, [section]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  // Automatically retry when the user comes back to the tab or the network
  // reconnects — usually right after the backend has been (re)started.
  useEffect(() => {
    if (!error || loading) return;
    const retry = () => {
      resetApiBaseUrlDiscovery();
      void fetchAccounts();
    };
    window.addEventListener('focus', retry);
    window.addEventListener('online', retry);
    return () => {
      window.removeEventListener('focus', retry);
      window.removeEventListener('online', retry);
    };
  }, [error, loading, fetchAccounts]);

  const retryLoad = () => {
    resetApiBaseUrlDiscovery();
    void fetchAccounts();
  };

  const openCreate = () => {
    setEditing(null);
    setName('');
    setDescription('');
    setDialogOpen(true);
  };

  const openEdit = (account: Account) => {
    setEditing(account);
    setName(account.name);
    setDescription(account.description || '');
    setDialogOpen(true);
  };

  const saveAccount = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      if (editing) {
        const updated = await updateAccount(editing.id, {
          name: name.trim(),
          description,
        });
        setAccounts((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
        toast.success('Account updated');
      } else {
        const created = await createAccount({
          name: name.trim(),
          description,
          section,
        });
        setAccounts((prev) =>
          [...prev, created].sort((a, b) => a.name.localeCompare(b.name))
        );
        toast.success('Account created');
      }
      setDialogOpen(false);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: Record<string, unknown> } })?.response
          ?.data;
      const message =
        detail && typeof detail === 'object'
          ? Object.values(detail).flat().join(' ')
          : 'Failed to save account';
      toast.error(String(message));
    } finally {
      setSaving(false);
    }
  };

  const removeAccount = async (account: Account) => {
    try {
      await deleteAccount(account.id);
      if (getStoredAccountId(section) === account.id) {
        clearStoredAccount(section);
      }
      setAccounts((prev) => prev.filter((item) => item.id !== account.id));
      toast.success(`Deleted "${account.name}"`);
    } catch {
      toast.error('Failed to delete account');
    }
  };

  const enterAccount = (account: Account) => {
    setStoredAccount(section, account.id, account.name);
    router.push(withAccount(`/${section}/dashboard`, account.id));
  };

  const SectionIcon = section === 'youtube' ? Video : Film;
  const title = section === 'youtube' ? 'YouTube Accounts' : 'Facebook Pages';

  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <SectionIcon className="h-6 w-6 text-primary" />
            {title}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Choose an account to work in. Every account has its own projects,
            gallery and settings.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          New {section === 'youtube' ? 'Account' : 'Page'}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <p className="text-sm text-destructive flex-1">{error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={retryLoad}
            disabled={loading}
            className="shrink-0"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Retry
          </Button>
        </div>
      )}


      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-56" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-9 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : accounts.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 mb-4">
              <UserRound className="h-7 w-7 text-primary" />
            </div>
            <h2 className="text-lg font-semibold">No accounts yet</h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              Create the first {section === 'youtube' ? 'YouTube account' : 'Facebook page'} for{' '}
              {SECTION_LABELS[section]} and start adding projects.
            </p>
            <Button className="mt-5" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Create account
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {accounts.map((account) => (
            <Card
              key={account.id}
              className="group cursor-pointer transition-all hover:ring-2 hover:ring-primary/25 hover:shadow-lg hover:shadow-primary/5"
              onClick={() => enterAccount(account)}
            >
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary shrink-0">
                      <UserRound className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <CardTitle className="text-base truncate">
                        {account.name}
                      </CardTitle>
                      <CardDescription className="truncate">
                        {account.description || 'No description'}
                      </CardDescription>
                    </div>
                  </div>
                  <div
                    className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => openEdit(account)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Delete &quot;{account.name}&quot;?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            This permanently deletes the account, all of its
                            projects, segments and media files. This cannot be
                            undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            onClick={() => removeAccount(account)}
                          >
                            Delete account
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 mb-4">
                  <Badge variant="secondary" className="gap-1">
                    <FolderKanban className="h-3 w-3" />
                    {account.project_count} project
                    {account.project_count === 1 ? '' : 's'}
                  </Badge>
                  <Badge variant="outline" className="gap-1">
                    <Film className="h-3 w-3" />
                    {account.gallery_count} rendered
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Created {formatDate(account.created_at)}</span>
                  <span className="inline-flex items-center gap-1 font-medium text-primary">
                    Open account
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing
                ? 'Edit account'
                : `New ${section === 'youtube' ? 'YouTube account' : 'Facebook page'}`}
            </DialogTitle>
            <DialogDescription>
              Accounts keep projects, galleries and storage completely separate.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label htmlFor="account-name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="account-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={
                  section === 'youtube' ? 'e.g. Mystery Channel' : 'e.g. Daily Facts Page'
                }
                autoFocus
                onKeyDown={(event) => {
                  if (event.key === 'Enter') saveAccount();
                }}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="account-description" className="text-sm font-medium">
                Description <span className="text-muted-foreground">(optional)</span>
              </label>
              <textarea
                id="account-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                placeholder="What kind of content lives in this account?"
                className="flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm resize-y"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button onClick={saveAccount} disabled={saving || !name.trim()}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving…
                </>
              ) : editing ? (
                'Save changes'
              ) : (
                'Create account'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
