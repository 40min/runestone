import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import Login from './Login';
import { AuthProvider } from '../../context/AuthContext';

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

    expect(screen.getByText('Login')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
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

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'password123');
    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/auth/token',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
        })
      );
    });

    expect(screen.queryByText('Logging in...')).not.toBeInTheDocument();
  });

  it('handles login failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    });

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');
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

    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, '12345'); // Less than 6 characters
    await userEvent.click(loginButton);

    expect(screen.getByText('Password must be at least 6 characters')).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('shows loading state during login', async () => {
    (global.fetch as any).mockImplementation(() =>
      new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'token' }),
      }), 100))
    );

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');
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

    const passwordInput = screen.getByLabelText('Password');
    const loginButton = screen.getByRole('button', { name: 'Login' });

    await userEvent.type(passwordInput, '12345'); // Trigger validation error
    await userEvent.click(loginButton);

    expect(screen.getByText('Password must be at least 6 characters')).toBeInTheDocument();

    // Clear error and try network error
    await userEvent.type(passwordInput, '6'); // Now valid length
    await userEvent.click(loginButton);

    // Mock network error
    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

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

  it('prevents form submission on button click', async () => {
    const mockPreventDefault = vi.fn();
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const loginButton = screen.getByRole('button', { name: 'Login' });

    // Simulate form submission
    fireEvent.click(loginButton, { preventDefault: mockPreventDefault });

    expect(mockPreventDefault).toHaveBeenCalled();
  });

  it('requires email and password fields', () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');

    expect(emailInput).toBeRequired();
    expect(passwordInput).toBeRequired();
  });
});
