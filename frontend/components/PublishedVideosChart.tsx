'use client';

import { useMemo, useState } from 'react';
import { BarChart3 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { GalleryItem } from '@/lib/types';
import { cn } from '@/lib/utils';

type ChartMode = 'day' | 'month' | 'year' | 'custom';
type Granularity = 'day' | 'month' | 'year';

interface Bucket {
  key: string;
  label: string;
  count: number;
}

const MODES: Array<{ value: ChartMode; label: string }> = [
  { value: 'day', label: 'Day' },
  { value: 'month', label: 'Month' },
  { value: 'year', label: 'Year' },
  { value: 'custom', label: 'Custom' },
];

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return startOfDay(next);
}

function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth() + 1}`;
}

function yearKey(date: Date): string {
  return String(date.getFullYear());
}

function keyFor(date: Date, granularity: Granularity): string {
  if (granularity === 'day') return dayKey(date);
  if (granularity === 'month') return monthKey(date);
  return yearKey(date);
}

function labelFor(date: Date, granularity: Granularity): string {
  if (granularity === 'day') {
    return `${MONTHS[date.getMonth()]} ${date.getDate()}`;
  }
  if (granularity === 'month') {
    return `${MONTHS[date.getMonth()]} '${String(date.getFullYear()).slice(-2)}`;
  }
  return String(date.getFullYear());
}

function buildBuckets(
  start: Date,
  end: Date,
  granularity: Granularity,
): Bucket[] {
  const buckets: Bucket[] = [];
  if (granularity === 'day') {
    for (let cursor = startOfDay(start); cursor <= end; cursor = addDays(cursor, 1)) {
      buckets.push({
        key: dayKey(cursor),
        label: labelFor(cursor, granularity),
        count: 0,
      });
    }
    return buckets;
  }
  if (granularity === 'month') {
    const first = new Date(start.getFullYear(), start.getMonth(), 1);
    for (let cursor = first; cursor <= end; cursor = addMonths(cursor, 1)) {
      buckets.push({
        key: monthKey(cursor),
        label: labelFor(cursor, granularity),
        count: 0,
      });
    }
    return buckets;
  }
  for (
    let year = start.getFullYear();
    year <= end.getFullYear();
    year += 1
  ) {
    const cursor = new Date(year, 0, 1);
    buckets.push({
      key: yearKey(cursor),
      label: labelFor(cursor, granularity),
      count: 0,
    });
  }
  return buckets;
}

function parseDateInput(value: string): Date | null {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function toInputValue(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;
}

interface PublishedVideosChartProps {
  /** Only published gallery items should be passed in. */
  items: GalleryItem[];
  className?: string;
}

/**
 * Publishing-activity bar chart for one account.
 *
 * The default view is the last 12 months.  Day, Year and a custom date range
 * are also available; a custom range automatically picks daily, monthly or
 * yearly buckets based on its length.
 */
export function PublishedVideosChart({
  items,
  className,
}: PublishedVideosChartProps) {
  const today = useMemo(() => startOfDay(new Date()), []);
  const [mode, setMode] = useState<ChartMode>('month');
  const [customStart, setCustomStart] = useState(() => toInputValue(addDays(today, -29)));
  const [customEnd, setCustomEnd] = useState(() => toInputValue(today));

  const { buckets, granularity, rangeLabel } = useMemo(() => {
    if (mode === 'custom') {
      const parsedStart = parseDateInput(customStart);
      const parsedEnd = parseDateInput(customEnd);
      let start = parsedStart ?? addDays(today, -29);
      let end = parsedEnd ?? today;
      if (start > end) [start, end] = [end, start];
      const spanDays = Math.floor((end.getTime() - start.getTime()) / DAY_MS) + 1;
      const customGranularity: Granularity =
        spanDays <= 62 ? 'day' : spanDays <= 731 ? 'month' : 'year';
      return {
        buckets: buildBuckets(start, end, customGranularity),
        granularity: customGranularity,
        rangeLabel: `${labelFor(start, 'day')} – ${labelFor(end, 'day')}`,
      };
    }

    let start: Date;
    const end = today;
    const currentGranularity: Granularity = mode;
    if (mode === 'day') {
      start = addDays(today, -13);
    } else if (mode === 'year') {
      start = new Date(today.getFullYear() - 4, 0, 1);
    } else {
      start = addMonths(new Date(today.getFullYear(), today.getMonth(), 1), -11);
    }
    return {
      buckets: buildBuckets(start, end, currentGranularity),
      granularity: currentGranularity,
      rangeLabel:
        currentGranularity === 'day'
          ? `${labelFor(start, 'day')} – ${labelFor(end, 'day')}`
          : currentGranularity === 'month'
            ? `${labelFor(start, 'month')} – ${labelFor(end, 'month')}`
            : `${start.getFullYear()} – ${end.getFullYear()}`,
    };
  }, [mode, customStart, customEnd, today]);

  const bucketsWithCounts = useMemo(() => {
    const byKey = new Map<string, number>();
    items.forEach((item) => {
      if (!item.published_at) return;
      const date = new Date(item.published_at);
      if (Number.isNaN(date.getTime())) return;
      const key = keyFor(date, granularity);
      byKey.set(key, (byKey.get(key) ?? 0) + 1);
    });
    return buckets.map((bucket) => ({
      ...bucket,
      count: byKey.get(bucket.key) ?? 0,
    }));
  }, [items, buckets, granularity]);

  const total = useMemo(
    () => bucketsWithCounts.reduce((sum, bucket) => sum + bucket.count, 0),
    [bucketsWithCounts],
  );

  const maxCount = Math.max(1, ...bucketsWithCounts.map((bucket) => bucket.count));

  return (
    <Card className={cn('gap-4 py-4', className)}>
      <CardHeader className="flex flex-col gap-3 px-4 pb-0 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-2">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <BarChart3 className="size-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold leading-tight">
              Published videos
            </h3>
            <p className="text-xs text-muted-foreground">
              {rangeLabel} · {granularity === 'day' ? 'per day' : granularity === 'month' ? 'per month' : 'per year'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div
            className="inline-flex items-center gap-0.5 rounded-md border p-0.5"
            role="group"
            aria-label="Published videos chart range"
          >
            {MODES.map((option) => (
              <Button
                key={option.value}
                size="sm"
                variant={mode === option.value ? 'secondary' : 'ghost'}
                className="h-7 px-2 text-xs"
                aria-pressed={mode === option.value}
                onClick={() => setMode(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
          <Badge variant="outline" className="h-6 tabular-nums">
            {total} published
          </Badge>
        </div>
      </CardHeader>

      {mode === 'custom' && (
        <div className="flex flex-wrap items-center gap-2 px-4">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            From
            <Input
              type="date"
              value={customStart}
              onChange={(event) => setCustomStart(event.target.value)}
              className="h-8 w-[140px] text-xs"
              aria-label="Published videos from date"
            />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            To
            <Input
              type="date"
              value={customEnd}
              onChange={(event) => setCustomEnd(event.target.value)}
              className="h-8 w-[140px] text-xs"
              aria-label="Published videos to date"
            />
          </label>
        </div>
      )}

      <CardContent className="px-4">
        {bucketsWithCounts.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No published videos in this range yet.
          </p>
        ) : (
          <div
            className="flex h-44 items-end gap-1.5 overflow-x-auto pb-1"
            role="img"
            aria-label={`Published videos, ${rangeLabel}, ${total} total`}
          >
            {bucketsWithCounts.map((bucket) => (
              <div
                key={bucket.key}
                className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1"
                title={`${bucket.label}: ${bucket.count} published`}
              >
                <span className="text-[10px] tabular-nums text-muted-foreground">
                  {bucket.count > 0 ? bucket.count : ''}
                </span>
                <div className="flex h-28 w-full items-end">
                  <div
                    role="img"
                    aria-label={`${bucket.label}: ${bucket.count} published`}
                    className={cn(
                      'w-full rounded-t transition-all',
                      bucket.count > 0
                        ? 'bg-primary/80 hover:bg-primary'
                        : 'bg-muted',
                    )}
                    style={{
                      height:
                        bucket.count > 0
                          ? `${Math.max(6, (bucket.count / maxCount) * 100)}%`
                          : '3px',
                    }}
                  />
                </div>
                <span className="w-full truncate text-center text-[9px] text-muted-foreground">
                  {bucket.label}
                </span>
              </div>
            ))}
          </div>
        )}

        {total === 0 && bucketsWithCounts.length > 0 && (
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Publish a gallery asset to start the chart.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
