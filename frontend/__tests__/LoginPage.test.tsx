import { render, screen } from '@testing-library/react';
import LoginPage from '@/app/login/page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock('@/lib/apiConfig', () => ({
  ensureApiBaseUrl: jest.fn().mockResolvedValue('http://localhost:8765'),
}));

describe('LoginPage branding', () => {
  it('shows the StoryFlow logo above the form', () => {
    render(<LoginPage />);

    const logo = screen.getByAltText('StoryFlow');
    expect(logo).toBeInTheDocument();
    expect(logo.getAttribute('src')).toContain('logo.png');
    expect(screen.getByText('StoryFlow Login')).toBeInTheDocument();
  });
});
