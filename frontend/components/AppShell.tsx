'use client';

import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  Settings,
  Film,
  FolderOpen,
  Layers,
  MonitorPlay,
  UserRound,
  ChevronDown,
  Users,
  Wand2,
  BookMarked,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { LogoutButton } from '@/components/LogoutButton';
import { SectionSwitcher } from '@/components/SectionSwitcher';
import { sectionFromPathname, sectionPath, type Section } from '@/lib/section';
import {
  getStoredAccountName,
  setStoredAccount,
  withAccount,
} from '@/lib/account';
import { getAccounts } from '@/lib/api';
import type { Account } from '@/lib/types';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';

// ── Navigation items (section-scoped) ──
interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  match: (path: string, section: Section) => boolean;
}

function buildNavItems(section: Section, accountId: string | null): NavItem[] {
  const base = sectionPath(section);
  // Never let withAccount() fall back to localStorage here: the server has no
  // localStorage, so doing so would produce different hrefs on the server and
  // during the client's hydration render.
  const hrefFor = (path: string) =>
    accountId ? withAccount(path, accountId) : path;
  const dashboard = accountId
    ? withAccount(sectionPath(section, '/dashboard'), accountId)
    : base;

  return [
    {
      label: 'Accounts',
      href: base,
      icon: Users,
      match: (path: string, activeSection: Section) =>
        path === sectionPath(activeSection),
    },
    {
      label: 'Dashboard',
      href: dashboard,
      icon: LayoutDashboard,
      match: (path: string, activeSection: Section) =>
        path === sectionPath(activeSection, '/dashboard'),
    },
    {
      label: 'Projects',
      href: hrefFor(sectionPath(section, '/projects')),
      icon: FolderOpen,
      match: (path: string, activeSection: Section) =>
        path.startsWith(sectionPath(activeSection, '/projects')),
    },
    {
      label: 'Bulk Create',
      href: hrefFor(sectionPath(section, '/bulk-create')),
      icon: Layers,
      match: (path: string, activeSection: Section) =>
        path.startsWith(sectionPath(activeSection, '/bulk-create')),
    },
    {
      label: 'Gallery',
      href: hrefFor(sectionPath(section, '/gallery')),
      icon: MonitorPlay,
      match: (path: string, activeSection: Section) =>
        path.startsWith(sectionPath(activeSection, '/gallery')),
    },
    {
      label: 'Script Craft',
      href: hrefFor(sectionPath(section, '/script-craft')),
      icon: Wand2,
      match: (path: string, activeSection: Section) =>
        path.startsWith(sectionPath(activeSection, '/script-craft')),
    },
    {
      label: 'Script Library',
      href: hrefFor(sectionPath(section, '/script-library')),
      icon: BookMarked,
      match: (path: string, activeSection: Section) =>
        path.startsWith(sectionPath(activeSection, '/script-library')),
    },
    {
      label: 'Settings',
      href: hrefFor(sectionPath(section, '/settings')),
      icon: Settings,
      match: (path: string, activeSection: Section) =>
        path.startsWith(sectionPath(activeSection, '/settings')),
    },
  ];
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const section = sectionFromPathname(pathname);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [accountName, setAccountName] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [mounted, setMounted] = useState(false);

  const isFullPage =
    pathname === '/login' ||
    pathname === '/select' ||
    pathname === '/selection';
  const isSectionLanding = pathname === sectionPath(section);
  const isProjectPage = /^\/(facebook|youtube)\/projects\/[^/]+/.test(pathname);

  // Hydrate the active account from the URL/localStorage and load the account
  // list for the switcher. Runs on every navigation so `?account=` wins.
  useEffect(() => {
    setMounted(true);
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const urlAccount = params.get('account');
    const id = urlAccount ||
      localStorage.getItem(`storyflow-account-${section}`);
    // Keep the stored selection in sync with an explicitly pinned account so
    // links that drop the query string still resolve to the same account.
    if (urlAccount) setStoredAccount(section, urlAccount);
    setAccountId(id);
    setAccountName(id ? getStoredAccountName(section) : null);

    getAccounts(section)
      .then((data) => {
        setAccounts(data.results);
        if (id) {
          const match = data.results.find((item) => item.id === id);
          if (match) setAccountName(match.name);
        }
      })
      .catch(() => {
        // Account switcher is non-critical; pages surface their own errors.
      });
  }, [pathname, section]);

  // Keep the account chip in sync with browser back/forward navigation.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onPopState = () => {
      const params = new URLSearchParams(window.location.search);
      const id = params.get('account') ||
        localStorage.getItem(`storyflow-account-${section}`);
      setAccountId(id);
      setAccountName(id ? getStoredAccountName(section) : null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [section]);

  // Simple local auth guard
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const isAuthed = localStorage.getItem('storyflow_authenticated') === 'true';
    if (!isAuthed && pathname !== '/login') {
      router.replace('/login');
    }
  }, [pathname, router]);

  // Every account-scoped page needs a selected account. Without one, send the
  // user back to the account picker for this side instead of leaking a mixed
  // cross-account list.
  useEffect(() => {
    if (!mounted || isFullPage || isSectionLanding) return;
    if (!accountId) {
      router.replace(sectionPath(section));
    }
  }, [accountId, isFullPage, isSectionLanding, mounted, router, section]);

  const switchAccount = useCallback(
    (account: Account) => {
      setStoredAccount(section, account.id, account.name);
      // Update immediately so the chip and nav links use the new account even
      // when the dashboard is already open (pathname does not change).
      setAccountId(account.id);
      setAccountName(account.name);
      // A full reload guarantees every page (including the dashboard) refetches
      // with the newly selected account instead of keeping the previous
      // account's data in client state.
      const target = withAccount(
        sectionPath(section, '/dashboard'),
        account.id,
      );
      if (typeof window !== 'undefined') {
        window.location.assign(target);
      } else {
        router.push(target);
      }
    },
    [router, section],
  );

  if (isFullPage) {
    return <>{children}</>;
  }

  // The account picker is the entry point for a section.  Other pages cannot
  // work until an account is chosen, so the full navigation is hidden here and
  // only the logout control is shown.
  if (isSectionLanding) {
    return (
      <div className="flex min-h-screen flex-col bg-background">
        <div className="flex h-14 shrink-0 items-center justify-end px-4">
          <LogoutButton />
        </div>
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    );
  }

  const navItems = buildNavItems(section, accountId);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* ── Top navigation bar (unique per section, present on every page) ── */}
      <header className="relative z-30 flex h-14 shrink-0 items-center gap-4 overflow-hidden border-b bg-sidebar px-4 text-sidebar-foreground">
        {/* Brand */}
        <Link
          href="/select"
          className="flex items-center gap-2.5 shrink-0 rounded-md px-1 py-1 transition-opacity hover:opacity-90"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Film className="h-4 w-4" />
          </div>
          <span className="hidden text-sm font-semibold tracking-tight sm:inline">
            StoryFlow
          </span>
        </Link>

        <div className="h-6 w-px bg-sidebar-border/60 shrink-0" />

        {/* Section navigation */}
        <nav className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto overflow-y-hidden">
          {navItems.map((item) => {
            const isActive = item.match(pathname, section);
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  'relative flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="hidden md:inline">{item.label}</span>
                {isActive && (
                  <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-primary" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right side: account, section switch, logout */}
        <div className="flex shrink-0 items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="gap-2 text-sidebar-foreground/90 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground max-w-44"
              >
                <UserRound className="h-4 w-4 shrink-0" />
                <span className="truncate hidden sm:inline">
                  {accountName || 'Select account'}
                </span>
                <ChevronDown className="h-3.5 w-3.5 opacity-60 shrink-0" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
              <DropdownMenuLabel className="flex items-center justify-between gap-2">
                <span>Switch account</span>
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  {section === 'youtube' ? 'YouTube' : 'Facebook'}
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {accounts.length === 0 ? (
                <DropdownMenuItem disabled>No accounts yet</DropdownMenuItem>
              ) : (
                accounts.map((account) => (
                  <DropdownMenuItem
                    key={account.id}
                    onClick={() => switchAccount(account)}
                    className={cn(
                      'flex items-center justify-between gap-2',
                      account.id === accountId && 'bg-accent',
                    )}
                  >
                    <span className="truncate">{account.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {account.project_count}
                    </span>
                  </DropdownMenuItem>
                ))
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href={sectionPath(section)} className="cursor-pointer">
                  <Users className="h-4 w-4 mr-2" />
                  Manage accounts
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <SectionSwitcher />
          <LogoutButton />
        </div>
      </header>

      {/* ── Main Content Area ── */}
      {isProjectPage ? (
        <main className="flex-1 overflow-hidden">{children}</main>
      ) : (
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      )}
    </div>
  );
}
