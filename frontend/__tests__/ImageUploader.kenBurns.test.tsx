import { render, screen, fireEvent } from '@testing-library/react';
import { ImageUploader } from '@/components/ImageUploader';
import type { KenBurnsConfig } from '@/lib/types';

const mockUpload = jest.fn().mockResolvedValue(undefined);
const mockRemove = jest.fn().mockResolvedValue(undefined);
const mockKenBurnsChange = jest.fn().mockResolvedValue(undefined);
const mockPreview = jest.fn();

const manualPan: KenBurnsConfig = {
  enabled: true,
  animation: 'pan',
  pan_mode: 'points',
  start: { x: 0.2, y: 0.5 },
  end: { x: 0.8, y: 0.5 },
  focal_point: { x: 0.5, y: 0.5 },
  area: null,
  zoom: 1.25,
};

function frameRect(width = 400, height = 225) {
  return {
    x: 0, y: 0, left: 0, top: 0, right: width, bottom: height,
    width, height, toJSON: () => ({}),
  };
}

function mockFramePointer(frame: HTMLElement) {
  jest.spyOn(frame, 'getBoundingClientRect').mockReturnValue(frameRect());
  frame.setPointerCapture = jest.fn();
  frame.releasePointerCapture = jest.fn();
  frame.hasPointerCapture = jest.fn(() => true);
}

function pointer(type: string, clientX: number, clientY: number) {
  return new MouseEvent(type, { bubbles: true, clientX, clientY });
}

describe('ImageUploader manual Ken Burns', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  function renderUploader(config: KenBurnsConfig = manualPan) {
    return render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        kenBurnsConfig={config}
        onKenBurnsConfigChange={mockKenBurnsChange}
        onRequestKenBurnsPreview={mockPreview}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />,
    );
  }

  it('shows the manual toggle and the pan tools by default', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        onKenBurnsConfigChange={mockKenBurnsChange}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />,
    );

    expect(
      screen.getByRole('checkbox', { name: /Manual Ken Burns/i }),
    ).not.toBeChecked();
    expect(
      screen.getByText(/Automatic Ken Burns/i),
    ).toBeInTheDocument();
  });

  it('enabling manual mode persists an enabled config', () => {
    render(
      <ImageUploader
        segmentId="seg-1"
        currentImage="/media/projects/test.jpg"
        isLocked={false}
        onKenBurnsConfigChange={mockKenBurnsChange}
        onUpload={mockUpload}
        onRemove={mockRemove}
      />,
    );

    fireEvent.click(screen.getByRole('checkbox', { name: /Manual Ken Burns/i }));

    expect(mockKenBurnsChange).toHaveBeenCalledWith(
      'seg-1',
      expect.objectContaining({ enabled: true, animation: 'pan' }),
    );
  });

  it('renders the zoom focal tool for a zoom preset', () => {
    renderUploader({ ...manualPan, animation: 'zoom_in' });

    expect(
      screen.getByRole('button', { name: /Set focal point/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('slider'),
    ).toHaveAttribute('aria-valuenow', '1.25');
    expect(
      screen.getByText(/Generate the TTS first/i),
    ).toBeInTheDocument();
  });

  it('places the pan start point where the user clicks', () => {
    renderUploader();
    const frame = screen.getByLabelText(/Render frame/);
    mockFramePointer(frame);

    fireEvent.click(screen.getByRole('button', { name: /Set start/i }));
    fireEvent(frame, pointer('pointerdown', 80, 112.5));

    expect(mockKenBurnsChange).toHaveBeenLastCalledWith(
      'seg-1',
      expect.objectContaining({
        enabled: true,
        start: { x: 0.2, y: 0.5 },
      }),
    );
  });

  it('draws a pan area and saves it in area mode', () => {
    renderUploader({ ...manualPan, pan_mode: 'area', area: null });
    const frame = screen.getByLabelText(/Render frame/);
    mockFramePointer(frame);

    fireEvent.click(screen.getByRole('button', { name: /Draw pan area/i }));
    fireEvent(frame, pointer('pointerdown', 40, 22.5));
    fireEvent(frame, pointer('pointermove', 240, 135));
    fireEvent(frame, pointer('pointerup', 240, 135));

    expect(mockKenBurnsChange).toHaveBeenLastCalledWith(
      'seg-1',
      expect.objectContaining({
        pan_mode: 'area',
        area: { x: 0.1, y: 0.1, w: 0.5, h: 0.5 },
      }),
    );
  });

  it('opens the preview from the manual Ken Burns panel', () => {
    renderUploader();

    fireEvent.click(
      screen.getByRole('button', { name: /Preview Ken Burns animation/i }),
    );

    expect(mockPreview).toHaveBeenCalledTimes(1);
  });

  it('resets back to the automatic planner', () => {
    renderUploader();

    fireEvent.click(screen.getByRole('button', { name: /^Auto$/i }));

    expect(mockKenBurnsChange).toHaveBeenLastCalledWith(
      'seg-1',
      expect.objectContaining({ enabled: false }),
    );
  });
});
