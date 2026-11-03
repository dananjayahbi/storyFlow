import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ScriptCraftPage } from '@/components/ScriptCraftPage';
import type { ChatSession } from '@/lib/types';

const mockPath = '/facebook/script-craft';
const mockStream = jest.fn();

jest.mock('next/navigation', () => ({
  usePathname: () => mockPath,
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock('@/lib/useAccountId', () => ({
  useAccountId: () => 'account-1',
}));

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn(),
  },
}));

jest.mock('@/lib/chat', () => ({
  streamChatSession: (...args: unknown[]) => mockStream(...args),
}));

const session: ChatSession = {
  id: 'session-1',
  account: 'account-1',
  section: 'facebook',
  title: 'Ocean chat',
  summary: '',
  messages: [
    {
      id: 'm1',
      role: 'user',
      content: 'Write an ocean script',
      created_at: '2026-01-01T00:00:00+00:00',
    },
    {
      id: 'm2',
      role: 'assistant',
      content: 'Added the first page.',
      thinking: 'Planning the beats.',
      tools: [{ name: 'create_script', status: 'completed', label: 'Wrote page 1' }],
      created_at: '2026-01-01T00:00:01+00:00',
    },
  ],
  scripts: [
    {
      id: 'page-1',
      title: 'Ocean one',
      pitch: 'ocean',
      content: {
        title: 'Ocean one',
        segments: [
          { text_content: 'First beat.', image_prompt: 'Ocean at dusk' },
          { text_content: 'Second beat.', image_prompt: 'Deep water' },
        ],
      },
      model: 'test-model',
      created_at: '2026-01-01T00:00:00+00:00',
      updated_at: '2026-01-01T00:00:00+00:00',
    },
    {
      id: 'page-2',
      title: 'Second page',
      pitch: 'ocean two',
      content: {
        title: 'Second page',
        segments: [{ text_content: 'Another beat.', image_prompt: 'Storm' }],
      },
      model: 'test-model',
      created_at: '2026-01-01T00:01:00+00:00',
      updated_at: '2026-01-01T00:01:00+00:00',
    },
  ],
  pending_steer: '',
  stop_requested: false,
  compacted_at: null,
  message_count: 2,
  script_count: 2,
  last_message: 'Added the first page.',
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:01:00+00:00',
};

const apiMock = {
  getAIConfig: jest.fn(),
  getChatSessions: jest.fn(),
  getChatSession: jest.fn(),
  createChatSession: jest.fn(),
  compactChatSession: jest.fn(),
  deleteChatSession: jest.fn(),
  steerChatSession: jest.fn(),
  stopChatSession: jest.fn(),
  saveScript: jest.fn(),
};

jest.mock('@/lib/api', () => ({
  getAIConfig: (...args: unknown[]) => apiMock.getAIConfig(...args),
  getChatSessions: (...args: unknown[]) => apiMock.getChatSessions(...args),
  getChatSession: (...args: unknown[]) => apiMock.getChatSession(...args),
  createChatSession: (...args: unknown[]) => apiMock.createChatSession(...args),
  compactChatSession: (...args: unknown[]) => apiMock.compactChatSession(...args),
  deleteChatSession: (...args: unknown[]) => apiMock.deleteChatSession(...args),
  steerChatSession: (...args: unknown[]) => apiMock.steerChatSession(...args),
  stopChatSession: (...args: unknown[]) => apiMock.stopChatSession(...args),
  saveScript: (...args: unknown[]) => apiMock.saveScript(...args),
}));

describe('ScriptCraftPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    jest.clearAllMocks();
    mockStream.mockResolvedValue(undefined);
    apiMock.getAIConfig.mockResolvedValue({
      model: 'test-model',
      system_prompt: '',
      default_model: '',
      base_url: 'http://localhost:11434/v1',
      api_key: '',
      temperature: 0.7,
      apply_to_all: false,
      search_enabled: true,
      search_provider: 'duckduckgo',
      search_brave_api_key: '',
      search_region: 'wt-wt',
    });
    apiMock.getChatSessions.mockResolvedValue([session]);
    apiMock.getChatSession.mockResolvedValue(session);
    apiMock.compactChatSession.mockResolvedValue({
      summary: 'Summary',
      compacted_at: '2026-01-02T00:00:00+00:00',
      message_count: 2,
    });
  });

  it('restores the last session and renders tool activity and thinking', async () => {
    render(<ScriptCraftPage />);

    expect(await screen.findByText('Ocean chat')).toBeInTheDocument();
    expect(screen.getByText('Added the first page.')).toBeInTheDocument();
    expect(screen.getByText('Wrote page 1')).toBeInTheDocument();
    expect(screen.getByText('Thinking')).toBeInTheDocument();
    expect(screen.getByText('Planning the beats.')).toBeInTheDocument();
  });

  it('shows every script as a book page and switches pages', async () => {
    render(<ScriptCraftPage />);

    const pageTwo = await screen.findByRole('button', { name: /2\.\s*Second page/i });
    fireEvent.click(pageTwo);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Second page' })).toBeInTheDocument();
    });
  });

  it('rewrites a selected block with the script and segment context', async () => {
    render(<ScriptCraftPage />);

    const rewriteButtons = await screen.findAllByRole('button', { name: /^Rewrite$/i });
    fireEvent.click(rewriteButtons[0]);

    await waitFor(() => {
      expect(mockStream).toHaveBeenCalledTimes(1);
    });
    const payload = mockStream.mock.calls[0][0];
    expect(payload.selection).toEqual({ script_id: 'page-2', segment_index: 1 });
    expect(payload.message).toContain('Rewrite segment 1');
  });

  it('runs the /compact slash command', async () => {
    render(<ScriptCraftPage />);

    const textarea = await screen.findByPlaceholderText(/documentary script/i);
    fireEvent.change(textarea, { target: { value: '/compact' } });
    fireEvent.keyDown(textarea, { key: 'Enter' });

    await waitFor(() => {
      expect(apiMock.compactChatSession).toHaveBeenCalledWith('session-1');
    });
  });
});
