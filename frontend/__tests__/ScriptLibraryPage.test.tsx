import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ScriptLibraryPage } from '@/components/ScriptLibraryPage';
import type { Script } from '@/lib/types';

const mockPath = '/facebook/script-library';
const mockPush = jest.fn();
const mockImportProject = jest.fn();
const mockGetScripts = jest.fn();

jest.mock('next/navigation', () => ({
  usePathname: () => mockPath,
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
}));

jest.mock('@/lib/useAccountId', () => ({
  useAccountId: () => 'account-1',
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

jest.mock('@/lib/api', () => ({
  getScripts: (...args: unknown[]) => mockGetScripts(...args),
  deleteScript: jest.fn(),
  importProject: (...args: unknown[]) => mockImportProject(...args),
}));

const script: Script = {
  id: 'script-1',
  account: 'account-1',
  section: 'facebook',
  title: 'World War 2',
  pitch: 'A documentary about WW2',
  content: {
    title: 'World War 2',
    segments: [
      { text_content: 'First beat.', image_prompt: 'Storm clouds' },
      { text_content: 'Second beat.', image_prompt: 'City at dawn' },
    ],
  },
  model_used: 'test-model',
  segment_count: 2,
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-02T00:00:00+00:00',
};

describe('ScriptLibraryPage create project', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetScripts.mockResolvedValue([script]);
    mockImportProject.mockResolvedValue({ id: 'project-1' });
  });

  it('opens a title dialog and creates a project from the script', async () => {
    render(<ScriptLibraryPage />);

    const createButtons = await screen.findAllByRole('button', { name: /^Create$/i });
    fireEvent.click(createButtons[0]);

    const titleInput = await screen.findByLabelText('Project title');
    expect(titleInput).toHaveValue('World War 2');
    fireEvent.change(titleInput, { target: { value: 'WW2 - New Cut' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Project/i }));

    await waitFor(() => {
      expect(mockImportProject).toHaveBeenCalledWith({
        format: 'json',
        title: 'WW2 - New Cut',
        section: 'facebook',
        account: 'account-1',
        segments: [
          { text_content: 'First beat.', image_prompt: 'Storm clouds' },
          { text_content: 'Second beat.', image_prompt: 'City at dawn' },
        ],
      });
    });
    expect(mockPush).toHaveBeenCalledWith(
      '/facebook/projects/project-1?account=account-1'
    );
  });

  it('keeps the original title when the field is left unchanged', async () => {
    render(<ScriptLibraryPage />);

    const createButtons = await screen.findAllByRole('button', { name: /^Create$/i });
    fireEvent.click(createButtons[0]);
    fireEvent.click(await screen.findByRole('button', { name: /Create Project/i }));

    await waitFor(() => {
      expect(mockImportProject.mock.calls[0][0].title).toBe('World War 2');
    });
  });
});
