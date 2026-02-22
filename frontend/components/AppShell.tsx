'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  Settings,
  Film,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ── Sidebar collapsed state persistence ──
const SIDEBAR_KEY = 'storyflow-sidebar-collapsed';

function getInitialCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(SIDEBAR_KEY) === 'true';
  } catch {
    return false;
  }
}

// ── Navigation items ──
const NAV_ITEMS = [
  {
    label: 'Dashboard',
    href: '/',
    icon: LayoutDashboard,
    match: (path: string) => path === '/',
  },
  {
    label: 'Settings',
    href: '/settings',
    icon: Settings,
    match: (path: string) => path === '/settings',
  },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Hydrate collapsed state from localStorage after mount
  useEffect(() => {
    setCollapsed(getInitialCollapsed());
    setMounted(true);
  }, []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_KEY, String(next));
      } catch { /* no-op */ }
      return next;
    });
  }, []);

  // Check if we're on the Timeline Editor page (project detail)
  const isProjectPage = pathname.startsWith('/projects/');

  // On project pages, hide the global sidebar entirely — the page has its own layout
  if (isProjectPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* ── Global Sidebar ── */}
      <aside
        className={cn(
          'flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-200 ease-in-out shrink-0',
          mounted
            ? collapsed ? 'w-16' : 'w-56'
            : 'w-56'  // default before hydration to avoid layout shift
        )}
      >
        {/* ── Brand ── */}
        <div className={cn(
          'flex items-center border-b h-14 px-3 shrink-0',
          collapsed ? 'justify-center' : 'gap-2.5'
        )}>
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground shrink-0">
            <Film className="h-4 w-4" />
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm tracking-tight truncate">
              StoryFlow
            </span>
          )}
        </div>

        {/* ── Navigation ── */}
        <nav className="flex-1 px-2 py-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = item.match(pathname);
            const link = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                  collapsed && 'justify-center px-2'
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href} delayDuration={0}>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return link;
          })}
        </nav>

        {/* ── Collapse Toggle ── */}
        <div className="border-t px-2 py-2 shrink-0">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={toggleCollapsed}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium w-full transition-colors',
                  'text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                  collapsed && 'justify-center px-2'
                )}
              >
                {collapsed ? (
                  <ChevronRight className="h-4 w-4 shrink-0" />
                ) : (
                  <>
                    <ChevronLeft className="h-4 w-4 shrink-0" />
                    <span>Collapse</span>
                  </>
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            </TooltipContent>
          </Tooltip>
        </div>
      </aside>

      {/* ── Main Content Area ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* ── Top Bar ── */}
        <header className="flex items-center h-14 border-b bg-background px-6 shrink-0">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-medium text-muted-foreground">
              {NAV_ITEMS.find((n) => n.match(pathname))?.label || 'StoryFlow'}
            </h1>
          </div>
        </header>

        {/* ── Page Content ── */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
