import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ImagePromptDisplay } from '@/components/ImagePromptDisplay';
import { TooltipProvider } from '@/components/ui/tooltip';

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
});

function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('ImagePromptDisplay', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders prompt text', () => {
    renderWithTooltip(<ImagePromptDisplay prompt="A sunset over mountains" />);
    expect(screen.getByText('A sunset over mountains')).toBeInTheDocument();
    expect(screen.getByText('Image Prompt')).toBeInTheDocument();
  });

  it('copy button calls navigator.clipboard.writeText', async () => {
    renderWithTooltip(<ImagePromptDisplay prompt="A sunset over mountains" />);
    const copyButton = screen.getByRole('button');
    fireEvent.click(copyButton);
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        'A sunset over mountains'
      );
    });
  });

  it('shows copied feedback after click', async () => {
    renderWithTooltip(<ImagePromptDisplay prompt="A sunset over mountains" />);
    const copyButton = screen.getByRole('button');
    fireEvent.click(copyButton);
    // After clicking, the Check icon replaces the ClipboardCopy icon
    await waitFor(() => {
      // The Check icon should now be rendered (svg with lucide-check class)
      const checkIcon = copyButton.querySelector('.lucide-check');
      expect(checkIcon).toBeInTheDocument();
    });
  });

  it('empty prompt shows placeholder text', () => {
    renderWithTooltip(<ImagePromptDisplay prompt="" />);
    expect(screen.getByText('No image prompt')).toBeInTheDocument();
  });
});
