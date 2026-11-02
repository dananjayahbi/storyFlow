import { act, render, screen } from '@testing-library/react';
import { AppShell } from '@/components/AppShell';

let mockPath = '/facebook/dashboard';

jest.mock('next/navigation', () => ({
  usePathname: () => mockPath,
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock('@/lib/api', () => ({
  getAccounts: jest.fn().mockResolvedValue({ results: [] }),
}));

describe('AppShell header', () => {
  beforeEach(() => {
    mockPath = '/facebook/dashboard';
    window.localStorage.setItem('storyflow_authenticated', 'true');
    window.localStorage.setItem('storyflow-account-facebook', 'account-1');
  });

  it('shows only the logout control on the accounts page', async () => {
    mockPath = '/facebook';
    const { container } = render(
      <AppShell>
        <div>account picker</div>
      </AppShell>
    );
    await act(async () => {});

    expect(container.querySelector('header')).toBeNull();
    expect(screen.getByText('account picker')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
    expect(screen.queryByText('Dashboard')).toBeNull();
    expect(screen.queryByText('Settings')).toBeNull();
  });

  it('does not create a vertical scrollbar in the navigation rail', async () => {
    const { container } = render(
      <AppShell>
        <div>page</div>
      </AppShell>
    );
    await act(async () => {});

    const nav = container.querySelector('header nav');
    expect(nav).not.toBeNull();
    expect(nav?.className).toContain('overflow-y-hidden');
  });

  it('keeps the active underline inside the nav item', async () => {
    const { getByText } = render(
      <AppShell>
        <div>page</div>
      </AppShell>
    );
    await act(async () => {});

    const dashboard = getByText('Dashboard').closest('a');
    expect(dashboard).not.toBeNull();
    const indicator = dashboard?.querySelector('span.absolute');
    expect(indicator).not.toBeNull();
    expect(indicator?.className).toContain('bottom-0');
    expect(indicator?.className).not.toContain('-bottom-');
  });
});
