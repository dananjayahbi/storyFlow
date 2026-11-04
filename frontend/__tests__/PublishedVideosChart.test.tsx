import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PublishedVideosChart } from '@/components/PublishedVideosChart';
import type { GalleryItem } from '@/lib/types';

function item(id: string, publishedAt: Date | null, status = 'published'): GalleryItem {
  return {
    id,
    project_id: `project-${id}`,
    project_title: `Project ${id}`,
    title: `Video ${id}`,
    status: status as GalleryItem['status'],
    status_label: status,
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-01T00:00:00+00:00',
    published_at: publishedAt ? publishedAt.toISOString() : null,
    resolution_width: 1080,
    resolution_height: 1920,
    framerate: 30,
    segment_count: 5,
    file_size: 1024,
    duration: 30,
    stream_url: `/api/gallery/${id}/stream/`,
    download_url: `/api/gallery/${id}/download/`,
  };
}

function monthsAgo(months: number): Date {
  const date = new Date();
  date.setDate(1);
  date.setMonth(date.getMonth() - months);
  return date;
}

function daysAgo(days: number): Date {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date;
}

function toInputValue(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;
}

const items = [
  item('today', daysAgo(1)),
  item('two-months', monthsAgo(2)),
  item('fourteen-months', monthsAgo(14)),
];

describe('PublishedVideosChart', () => {
  it('defaults to the last 12 months and counts published videos', () => {
    render(<PublishedVideosChart items={items} />);

    expect(screen.getByText('2 published')).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: /Published videos, .* 2 total/ }),
    ).toBeInTheDocument();
    // One bar per month in the default range.
    expect(screen.getAllByRole('img', { name: /published$/ })).toHaveLength(12);
  });

  it('switches to day and year ranges', async () => {
    const user = userEvent.setup();
    render(<PublishedVideosChart items={items} />);

    await user.click(screen.getByRole('button', { name: 'Day' }));
    expect(screen.getByText('1 published')).toBeInTheDocument();
    expect(screen.getAllByRole('img', { name: /published$/ })).toHaveLength(14);

    await user.click(screen.getByRole('button', { name: 'Year' }));
    expect(screen.getByText('3 published')).toBeInTheDocument();
    expect(screen.getAllByRole('img', { name: /published$/ })).toHaveLength(5);
  });

  it('filters by a custom date range', async () => {
    const user = userEvent.setup();
    render(<PublishedVideosChart items={items} />);

    await user.click(screen.getByRole('button', { name: 'Custom' }));

    fireEvent.change(screen.getByLabelText('Published videos from date'), {
      target: { value: toInputValue(monthsAgo(3)) },
    });
    fireEvent.change(screen.getByLabelText('Published videos to date'), {
      target: { value: toInputValue(new Date()) },
    });

    expect(screen.getByText('2 published')).toBeInTheDocument();
  });

  it('ignores items without a published date', () => {
    render(
      <PublishedVideosChart
        items={[...items, item('draft', null, 'rendered')]}
      />,
    );

    expect(screen.getByText('2 published')).toBeInTheDocument();
  });
});
