import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import Login from './Login';
import { AuthProvider } from '../../context/AuthContext';

// Mock config
vi.mock('../../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
global.fetch = vi.fn();

describe('Login', () => {
  const mockOnSwitchToRegister = vi.fn();

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form', () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Email\s+\*\s*$/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password\s+\*\s*$/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByText("Don't have an account? Register")).toBeInTheDocument();
  });

  it('handles successful login', async () => {
    const mockTokenResponse = { access_token: 'test-token' };
    const mockUserResponse = {
      id: 1,
      email: 'test@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 5
    };

    vi.mocked(global.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'password123');
    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8010/auth/token',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
        })
      );
    });

    expect(screen.queryByText('Logging in...')).not.toBeInTheDocument();
  });

  it('handles login failure', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    } as Response);

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'wrongpassword');
    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });

  it('validates password length', async () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, '12345'); // Less than 6 characters
    await userEvent.click(loginButton);

    expect(screen.getByText('Password must be at least 6 characters')).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('shows loading state during login', async () => {
    vi.mocked(global.fetch).mockImplementation(() =>
      new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'token' }),
      } as Response), 100))
    );

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'password123');
    await userEvent.click(loginButton);

    expect(screen.getByText('Logging in...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('Logging in...')).not.toBeInTheDocument();
    });
  });

  it('displays error messages', async () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(passwordInput, '12345'); // Trigger validation error
    await userEvent.click(loginButton);

    expect(screen.getByText('Password must be at least 6 characters')).toBeInTheDocument();

    // Clear error and try network error - need to wait for loading to finish
    await userEvent.clear(passwordInput);
    await userEvent.type(passwordInput, 'password123'); // Now valid length
    await userEvent.click(loginButton);

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText('Logging in...')).not.toBeInTheDocument();
    });

    // Mock network error for next attempt
    vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Network error'));

    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('calls onSwitchToRegister when register link is clicked', async () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const registerLink = screen.getByText("Don't have an account? Register");
    await userEvent.click(registerLink);

    expect(mockOnSwitchToRegister).toHaveBeenCalledTimes(1);
  });

  it('has submit button', async () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const loginButton = screen.getByRole('button', { name: 'Login' });

    // Button should be of type submit to submit the form
    expect(loginButton).toHaveAttribute('type', 'submit');
  });

  it('requires email and password fields', () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);

    expect(emailInput).toBeRequired();
    expect(passwordInput).toBeRequired();
  });
});
