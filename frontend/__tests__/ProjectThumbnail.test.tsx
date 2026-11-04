import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ProjectThumbnail } from '@/components/ProjectThumbnail';
import type { Project } from '@/lib/types';

const project: Project = {
  id: 'project-1',
  title: 'Cover Story',
  section: 'facebook',
  account: 'account-1',
  account_name: 'Default Account',
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-02T00:00:00+00:00',
  status: 'DRAFT',
  resolution_width: 1080,
  resolution_height: 1920,
  framerate: 30,
  segment_count: 4,
  thumbnail_url: 'http://example.test/media/cover.png',
  manual_thumbnail_url: 'http://example.test/media/cover.png',
  has_manual_thumbnail: true,
  thumbnail_source: 'manual',
};

describe('ProjectThumbnail upload controls', () => {
  it('does not open the surrounding project when the upload button is clicked', async () => {
    const user = userEvent.setup();
    const onOpen = jest.fn();
    const onUpload = jest.fn();

    render(
      <TooltipProvider>
        <div onClick={onOpen}>
          <ProjectThumbnail
            project={project}
            editable
            onUpload={onUpload}
          />
        </div>
      </TooltipProvider>,
    );

    await user.click(
      screen.getByRole('button', { name: /Upload thumbnail for Cover Story/i }),
    );

    expect(onOpen).not.toHaveBeenCalled();
    expect(onUpload).not.toHaveBeenCalled();
  });

  it('uploads the selected file without bubbling the input click', () => {
    const onOpen = jest.fn();
    const onUpload = jest.fn();
    const file = new File(['image'], 'cover.png', { type: 'image/png' });

    render(
      <TooltipProvider>
        <div onClick={onOpen}>
          <ProjectThumbnail
            project={project}
            editable
            onUpload={onUpload}
          />
        </div>
      </TooltipProvider>,
    );

    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).not.toBeNull();
    fireEvent.change(input as HTMLInputElement, {
      target: { files: [file] },
    });

    expect(onUpload).toHaveBeenCalledWith(file);
    expect(onOpen).not.toHaveBeenCalled();
  });
});
