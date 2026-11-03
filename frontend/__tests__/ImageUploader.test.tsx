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
