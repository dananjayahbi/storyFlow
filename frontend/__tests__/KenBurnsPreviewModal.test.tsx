import { fireEvent, render, screen } from '@testing-library/react';
import { KenBurnsPreviewModal } from '@/components/KenBurnsPreviewModal';
import type { KenBurnsConfig } from '@/lib/types';

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

function renderModal(
  overrides: Partial<React.ComponentProps<typeof KenBurnsPreviewModal>> = {},
) {
  const onOpenChange = jest.fn();
  render(
    <KenBurnsPreviewModal
      open
      onOpenChange={onOpenChange}
      image="/media/projects/test.jpg"
      config={manualPan}
      frameWidth={1920}
      frameHeight={1080}
      zoomIntensity={1.3}
      segmentIndex={0}
      duration={4.2}
      segmentLabel="#3"
      {...overrides}
    />,
  );
  return { onOpenChange };
}

describe('KenBurnsPreviewModal', () => {
  beforeEach(() => {
    jest.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 1);
    jest.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders the animation stage and transport controls', () => {
    renderModal();

    expect(
      screen.getByRole('heading', { name: /Ken Burns preview/i }),
    ).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: /Ken Burns animation preview/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Play preview/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Restart preview/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('slider', { name: /Preview position/i }),
    ).toBeInTheDocument();
    expect(screen.getByText('Pan')).toBeInTheDocument();
    expect(screen.queryByText(/No TTS audio yet/i)).not.toBeInTheDocument();
  });

  it('starts and pauses playback from the transport button', () => {
    renderModal();

    fireEvent.click(screen.getByRole('button', { name: /Play preview/i }));
    expect(
      screen.getByRole('button', { name: /Pause preview/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Pause preview/i }));
    expect(
      screen.getByRole('button', { name: /Play preview/i }),
    ).toBeInTheDocument();
  });

  it('warns when the TTS duration is not known yet', () => {
    renderModal({ duration: null });

    expect(screen.getByText(/No TTS audio yet/i)).toBeInTheDocument();
    expect(screen.getByText(/5 s estimate/i)).toBeInTheDocument();
  });

  it('previews the automatic planner when manual mode is disabled', () => {
    renderModal({ config: { ...manualPan, enabled: false } });

    expect(screen.getByText('Automatic')).toBeInTheDocument();
    expect(
      screen.getByText(/Automatic planner/i),
    ).toBeInTheDocument();
  });

  it('closes through the dialog close button', () => {
    const { onOpenChange } = renderModal();

    fireEvent.click(screen.getByRole('button', { name: /close/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('explains when there is no image to preview', () => {
    renderModal({ image: null });

    expect(
      screen.getByText(/Upload an image to preview/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('img', { name: /Ken Burns animation preview/i }),
    ).not.toBeInTheDocument();
  });
});
