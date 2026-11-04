import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SubtitlePositionModal } from '@/components/SubtitlePositionModal';

function renderModal(overrides: Partial<React.ComponentProps<typeof SubtitlePositionModal>> = {}) {
  const onSave = jest.fn().mockResolvedValue(undefined);
  const onOpenChange = jest.fn();
  render(
    <SubtitlePositionModal
      open
      onOpenChange={onOpenChange}
      yPosition={null}
      presetPosition="bottom"
      renderWidth={1080}
      renderHeight={1440}
      fontSize={48}
      subtitleColor="#FFFFFF"
      onSave={onSave}
      {...overrides}
    />,
  );
  return { onSave, onOpenChange };
}

describe('SubtitlePositionModal', () => {
  it('clamps an out-of-frame saved Y to the visible frame', () => {
    renderModal({ yPosition: 9999 });
    expect(
      screen.getByText(/Y Position \(top edge\): 1368px/),
    ).toBeInTheDocument();
  });

  it('Reset to bottom saves an explicit resolution-aware Y', async () => {
    const user = userEvent.setup();
    const { onSave, onOpenChange } = renderModal({ yPosition: 1321 });

    await user.click(screen.getByRole('button', { name: /Reset to bottom/i }));

    // 1440 - (48 + 2 x 12) - round(1440 * 0.08) = 1253.
    expect(onSave).toHaveBeenCalledWith(1253);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
