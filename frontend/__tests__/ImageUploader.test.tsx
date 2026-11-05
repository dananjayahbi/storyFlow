import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ImageUploader } from '@/components/ImageUploader';

describe('ImageUploader', () => {
  const mockUpload = jest.fn().mockResolvedValue(undefined);
  const mockRemove = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders drop zone when no image', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage={null}
        isLocked={false}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );
    expect(
      screen.getByText('Drop image here or click to browse')
    ).toBeInTheDocument();
  });

  it('renders image preview when image exists', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );
    expect(
      screen.getByAltText('Segment image cropped to the render frame')
    ).toBeInTheDocument();
  });

  it('uses the project aspect ratio and persisted focus for the frame', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        frameWidth={1080}
        frameHeight={1920}
        focusX={0.25}
        focusY={0.75}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    const frame = screen.getByLabelText(/Render frame 1080×1920/);
    expect(frame).toHaveStyle({ aspectRatio: '1080 / 1920' });

    const image = screen.getByAltText('Segment image cropped to the render frame');
    expect(image).toHaveStyle({ objectPosition: '25% 75%' });
  });

  it('shows a marked Ken Burns focus area and can clear it', () => {
    const onFocusAreaChange = jest.fn().mockResolvedValue(undefined);
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        focusArea={{ x: 0.2, y: 0.3, w: 0.4, h: 0.2 }}
        onFocusAreaChange={onFocusAreaChange}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    expect(screen.getByText('Ken Burns focus')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Mark Ken Burns focus area/i })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Clear focus area/i }));
    expect(onFocusAreaChange).toHaveBeenCalledWith('seg-1', null);
  });

  it('shows only the first legacy focus area from a stored list', () => {
    const onFocusAreasChange = jest.fn().mockResolvedValue(undefined);
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        focusAreas={[
          { x: 0.1, y: 0.1, w: 0.2, h: 0.2 },
          { x: 0.6, y: 0.5, w: 0.25, h: 0.3 },
        ]}
        onFocusAreasChange={onFocusAreasChange}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    expect(screen.getByText('Ken Burns focus')).toBeInTheDocument();
    expect(screen.queryByText('Ken Burns focus 2')).not.toBeInTheDocument();
    expect(
      screen.getByText(/keeps this area in frame/i)
    ).toBeInTheDocument();
  });

  it('clears the focus area through the list callback', () => {
    const onFocusAreasChange = jest.fn().mockResolvedValue(undefined);
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        focusAreas={[{ x: 0.1, y: 0.1, w: 0.2, h: 0.2 }]}
        onFocusAreasChange={onFocusAreasChange}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Clear focus area/i }));
    expect(onFocusAreasChange).toHaveBeenCalledWith('seg-1', []);
  });

  it('replaces the focus area instead of adding a second rectangle', () => {
    const onFocusAreasChange = jest.fn().mockResolvedValue(undefined);
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        onFocusAreasChange={onFocusAreasChange}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    const frame = screen.getByLabelText(/Render frame/);
    const rect = {
      x: 0, y: 0, left: 0, top: 0, right: 400, bottom: 225,
      width: 400, height: 225, toJSON: () => ({}),
    };
    jest.spyOn(frame, 'getBoundingClientRect').mockReturnValue(rect);
    (frame as HTMLElement).setPointerCapture = jest.fn();
    (frame as HTMLElement).releasePointerCapture = jest.fn();
    (frame as HTMLElement).hasPointerCapture = jest.fn(() => true);

    fireEvent.click(
      screen.getByRole('button', { name: /Mark Ken Burns focus area/i })
    );
    const pointer = (type: string, clientX: number, clientY: number) => (
      new MouseEvent(type, { bubbles: true, clientX, clientY })
    );
    fireEvent(frame, pointer('pointerdown', 80, 45));
    fireEvent(frame, pointer('pointermove', 200, 135));
    fireEvent(frame, pointer('pointerup', 200, 135));

    expect(onFocusAreasChange).toHaveBeenLastCalledWith('seg-1', [
      { x: 0.2, y: 0.2, w: 0.3, h: 0.4 },
    ]);

    fireEvent.click(
      screen.getByRole('button', { name: /Mark Ken Burns focus area/i })
    );
    fireEvent(frame, pointer('pointerdown', 40, 22.5));
    fireEvent(frame, pointer('pointermove', 120, 112.5));
    fireEvent(frame, pointer('pointerup', 120, 112.5));

    expect(onFocusAreasChange).toHaveBeenLastCalledWith('seg-1', [
      { x: 0.1, y: 0.1, w: 0.2, h: 0.4 },
    ]);
  });

  it('exposes the focus-area marking tool', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        onFocusAreaChange={jest.fn()}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    fireEvent.click(
      screen.getByRole('button', { name: /Mark Ken Burns focus area/i })
    );
    expect(
      screen.getByRole('button', { name: /Cancel focus area marking/i })
    ).toBeInTheDocument();
  });

  it('drop event triggers upload callback', async () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage={null}
        isLocked={false}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    const dropZone = screen.getByRole('button');
    const file = new File(['pixels'], 'photo.png', { type: 'image/png' });
    const dataTransfer = {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    };

    fireEvent.dragEnter(dropZone, { dataTransfer });
    fireEvent.dragOver(dropZone, { dataTransfer });
    fireEvent.drop(dropZone, { dataTransfer });

    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledWith('seg-1', file);
    });
  });

  it('click-to-browse triggers file input', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage={null}
        isLocked={false}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    // The drop zone is a clickable button - clicking should trigger hidden file input
    const dropZone = screen.getByRole('button');
    // Click should not throw
    fireEvent.click(dropZone);
    // File input should exist in DOM
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).toBeInTheDocument();
  });

  it('rejects non-image files with error message', async () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage={null}
        isLocked={false}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    const dropZone = screen.getByRole('button');
    const file = new File(['data'], 'doc.pdf', { type: 'application/pdf' });
    const dataTransfer = {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    };

    fireEvent.drop(dropZone, { dataTransfer });

    await waitFor(() => {
      expect(
        screen.getByText('Only JPEG, PNG, and WebP images are allowed.')
      ).toBeInTheDocument();
    });
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it('disables upload when locked', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage={null}
        isLocked={true}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />
    );

    const dropZone = screen.getByRole('button');
    const file = new File(['pixels'], 'photo.png', { type: 'image/png' });
    const dataTransfer = {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    };

    fireEvent.drop(dropZone, { dataTransfer });
    expect(mockUpload).not.toHaveBeenCalled();
  });
});
