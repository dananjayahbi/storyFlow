import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { MetadataManagementModal } from '@/components/MetadataManagementModal';
import type { ProjectDetail, ProjectThumbnail, Segment } from '@/lib/types';
import {
  deleteProjectThumbnailAsset,
  generateProjectDescription,
  generateProjectTitle,
  generateThumbnailPrompt,
  setActiveProjectThumbnail,
  updateProject,
  uploadProjectThumbnailAsset,
} from '@/lib/api';

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    info: jest.fn(),
    warning: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock('@/lib/api', () => ({
  generateThumbnailPrompt: jest.fn(),
  generateProjectTitle: jest.fn(),
  generateProjectDescription: jest.fn(),
  uploadProjectThumbnailAsset: jest.fn(),
  setActiveProjectThumbnail: jest.fn(),
  deleteProjectThumbnailAsset: jest.fn(),
  updateProject: jest.fn(),
}));

const mockGenerate = generateThumbnailPrompt as jest.Mock;
const mockGenerateTitle = generateProjectTitle as jest.Mock;
const mockGenerateDescription = generateProjectDescription as jest.Mock;
const mockUpload = uploadProjectThumbnailAsset as jest.Mock;
const mockActivate = setActiveProjectThumbnail as jest.Mock;
const mockDelete = deleteProjectThumbnailAsset as jest.Mock;
const mockUpdateProject = updateProject as jest.Mock;

function makeSegment(index: number, withImage = true): Segment {
  return {
    id: `seg-${index}`,
    project: 'project-1',
    sequence_index: index,
    text_content: `Narration for block ${index + 1}.`,
    image_prompt: `Visual direction ${index + 1}.`,
    image_file: withImage
      ? `/media/YouTube/account/project/images/block-${index}.png`
      : null,
    audio_file: null,
    audio_duration: null,
    is_locked: false,
  };
}

function makeProject(
  segments: Segment[],
  overrides: Partial<ProjectDetail> = {},
): ProjectDetail {
  return {
    id: 'project-1',
    title: 'Deep Sea Story',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    status: 'DRAFT',
    resolution_width: 1920,
    resolution_height: 1080,
    framerate: 30,
    output_path: null,
    segments,
    default_voice_id: 'af_bella',
    tts_speed: 1,
    subtitle_font_family: 'Arial',
    subtitle_font_size: 48,
    subtitle_font_color: '#FFFFFF',
    subtitle_position: 'bottom',
    subtitle_y_position: null,
    subtitle_font: '',
    subtitle_color: '#FFFFFF',
    subtitles_enabled: true,
    custom_font_file: null,
    zoom_intensity: 1.3,
    ken_burns_zoom: 1.2,
    transition_duration: 0.5,
    inter_segment_silence: 0.3,
    logo_enabled: false,
    active_logo: null,
    logo_scale: 0.15,
    logo_position: 'bottom-right',
    logo_opacity: 1,
    logo_margin: 20,
    outro_enabled: false,
    active_outro: null,
    bgm_enabled: false,
    active_bgm: null,
    bgm_gain_db: -18,
    bgm_ducking_db: -12,
    bgm_echo_percent: 0,
    bgm_crossfade_ms: 3000,
    tts_gain_db: 0,
    upscale_enabled: false,
    upscale_model: 'RealESRGAN_x4plus',
    upscale_denoise_strength: 0.5,
    thumbnails: [],
    thumbnail_system_prompt: '',
    ...overrides,
  };
}

function renderModal(project: ProjectDetail) {
  const onProjectRefreshed = jest.fn().mockResolvedValue(undefined);
  render(
    <MetadataManagementModal
      open
      onOpenChange={() => {}}
      project={project}
      onProjectRefreshed={onProjectRefreshed}
    />,
  );
  return { onProjectRefreshed };
}

describe('MetadataManagementModal', () => {
  beforeAll(() => {
    Object.defineProperty(global.URL, 'createObjectURL', {
      configurable: true,
      value: jest.fn(() => 'blob:preview'),
    });
    Object.defineProperty(global.URL, 'revokeObjectURL', {
      configurable: true,
      value: jest.fn(),
    });
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('keeps thumbnail generation locked until half the blocks have images', () => {
    const project = makeProject([
      makeSegment(0, true),
      makeSegment(1, false),
      makeSegment(2, false),
      makeSegment(3, false),
    ]);
    renderModal(project);

    expect(
      screen.getByText(/Thumbnail generation unlocks after the script is crafted/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Generate thumbnail prompt/i }),
    ).toBeDisabled();
  });

  it('selects the first five illustrated blocks by default', () => {
    const project = makeProject(
      Array.from({ length: 7 }, (_, index) => makeSegment(index, true)),
    );
    renderModal(project);

    expect(screen.getByText('5 selected')).toBeInTheDocument();
    const referenceButtons = screen.getAllByRole('button', {
      name: /Use block \d+ as a reference/i,
    });
    expect(referenceButtons).toHaveLength(7);
    expect(
      referenceButtons.filter(
        (button) => button.getAttribute('aria-pressed') === 'true',
      ),
    ).toHaveLength(5);
  });

  it('sends the selected blocks and returns a copyable prompt', async () => {
    const project = makeProject(
      Array.from({ length: 6 }, (_, index) => makeSegment(index, true)),
    );
    mockGenerate.mockResolvedValue({
      prompt: 'A dramatic abyss reveal.',
      model: 'test-model',
      used_segment_ids: [],
      external_image_count: 0,
      document_count: 0,
    });

    renderModal(project);
    fireEvent.click(
      screen.getByRole('button', { name: /Generate thumbnail prompt/i }),
    );

    await waitFor(() => expect(mockGenerate).toHaveBeenCalledTimes(1));
    const [projectId, payload] = mockGenerate.mock.calls[0];
    expect(projectId).toBe('project-1');
    expect(payload.segmentIds).toEqual([
      'seg-0',
      'seg-1',
      'seg-2',
      'seg-3',
      'seg-4',
    ]);
    await waitFor(() =>
      expect(
        screen.getByLabelText('Generated thumbnail prompt'),
      ).toHaveValue('A dramatic abyss reveal.'),
    );
  });

  it('expands and saves the editable system prompt', async () => {
    const project = makeProject([makeSegment(0), makeSegment(1)]);
    mockUpdateProject.mockResolvedValue({ ...project });
    const { onProjectRefreshed } = renderModal(project);

    fireEvent.click(
      screen.getByRole('button', { name: /System prompt/i }),
    );
    fireEvent.change(screen.getByLabelText('Thumbnail system prompt'), {
      target: { value: 'Use cold teal lighting.' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /Save system prompt/i }),
    );

    await waitFor(() =>
      expect(mockUpdateProject).toHaveBeenCalledWith('project-1', {
        thumbnail_system_prompt: 'Use cold teal lighting.',
      }),
    );
    expect(onProjectRefreshed).toHaveBeenCalled();
  });

  it('uploads a dropped thumbnail and refreshes the project cover', async () => {
    const project = makeProject([makeSegment(0), makeSegment(1)]);
    const created: ProjectThumbnail = {
      id: 'thumb-1',
      url: '/media/YouTube/account/project/thumbnails/thumb-1.png',
      prompt: '',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
    };
    mockUpload.mockResolvedValue(created);
    const { onProjectRefreshed } = renderModal(project);

    const file = new File(['image'], 'thumbnail.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText('Upload thumbnail image'), {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(mockUpload).toHaveBeenCalledWith('project-1', file, ''),
    );
    expect(onProjectRefreshed).toHaveBeenCalled();
    expect(await screen.findByText('1 saved')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('activates a saved thumbnail and deletes candidates', async () => {
    const thumbnails: ProjectThumbnail[] = [
      {
        id: 'thumb-1',
        url: '/media/first.png',
        prompt: '',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'thumb-2',
        url: '/media/second.png',
        prompt: '',
        is_active: false,
        created_at: '2026-01-02T00:00:00Z',
      },
    ];
    const project = makeProject([makeSegment(0), makeSegment(1)], {
      thumbnails,
    });
    mockActivate.mockResolvedValue({ ...thumbnails[1], is_active: true });
    mockDelete.mockResolvedValue(undefined);
    const { onProjectRefreshed } = renderModal(project);

    fireEvent.click(screen.getAllByRole('button', { name: /Make active/i })[0]);
    await waitFor(() =>
      expect(mockActivate).toHaveBeenCalledWith('project-1', 'thumb-2'),
    );

    fireEvent.click(screen.getAllByLabelText('Delete thumbnail')[1]);
    await waitFor(() =>
      expect(mockDelete).toHaveBeenCalledWith('project-1', 'thumb-2'),
    );
    expect(onProjectRefreshed).toHaveBeenCalled();
  });

  it('generates an upload-ready title and can promote it to the project title', async () => {
    const project = makeProject([makeSegment(0), makeSegment(1)], {
      title_system_prompt: 'Saved title prompt.',
      upload_title: '',
    });
    mockGenerateTitle.mockResolvedValue({
      title: 'The Secret Trench Nobody Explored',
      model: 'test-model',
    });
    mockUpdateProject.mockResolvedValue({
      ...project,
      title: 'The Secret Trench Nobody Explored',
    });
    const { onProjectRefreshed } = renderModal(project);

    fireEvent.click(screen.getByRole('tab', { name: 'Title' }));
    fireEvent.click(
      screen.getByRole('button', { name: /Title system prompt/i }),
    );
    fireEvent.change(screen.getByLabelText('Title system prompt'), {
      target: { value: 'Custom title prompt.' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /Save title prompt/i }),
    );
    await waitFor(() =>
      expect(mockUpdateProject).toHaveBeenCalledWith('project-1', {
        title_system_prompt: 'Custom title prompt.',
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: /^Generate title$/i }));

    await waitFor(() => expect(mockGenerateTitle).toHaveBeenCalledTimes(1));
    const [projectId, payload] = mockGenerateTitle.mock.calls[0];
    expect(projectId).toBe('project-1');
    expect(payload.systemPrompt).toBe('Custom title prompt.');
    await waitFor(() =>
      expect(screen.getByLabelText('Generated upload title')).toHaveValue(
        'The Secret Trench Nobody Explored',
      ),
    );

    fireEvent.click(
      screen.getByRole('button', { name: /Use as project title/i }),
    );
    await waitFor(() =>
      expect(mockUpdateProject).toHaveBeenCalledWith('project-1', {
        title: 'The Secret Trench Nobody Explored',
      }),
    );
    expect(onProjectRefreshed).toHaveBeenCalled();
  });

  it('generates a copyable SEO description separately from the title', async () => {
    const project = makeProject([makeSegment(0), makeSegment(1)], {
      description_system_prompt: 'Saved description prompt.',
    });
    mockGenerateDescription.mockResolvedValue({
      description:
        'The abyss hides a secret.\n\nWatch the full documentary.\n\n#ocean #documentary',
      model: 'test-model',
    });
    renderModal(project);

    fireEvent.click(screen.getByRole('tab', { name: 'Description' }));
    fireEvent.change(
      screen.getByLabelText('Your description instructions'),
      { target: { value: 'Mention the trench.' } },
    );
    fireEvent.click(
      screen.getByRole('button', { name: /^Generate description$/i }),
    );

    await waitFor(() =>
      expect(mockGenerateDescription).toHaveBeenCalledWith('project-1', {
        systemPrompt: 'Saved description prompt.',
        message: 'Mention the trench.',
        thumbnailPrompt: '',
      }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText('Generated description')).toHaveValue(
        'The abyss hides a secret.\n\nWatch the full documentary.\n\n#ocean #documentary',
      ),
    );
  });
});
