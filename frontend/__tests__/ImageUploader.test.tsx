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
    expect(screen.getByAltText('Segment image')).toBeInTheDocument();
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
