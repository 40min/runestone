import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import Register from './Register';
import { AuthProvider } from '../../context/AuthContext';
import { useAuthActions } from '../../hooks/useAuth';

// Mock config
vi.mock('../../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const mockNavigate = vi.fn();

// Mock React Router's useNavigate (since react-router-dom is not installed)
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock context
vi.mock('../../context/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({
    login: vi.fn(),
    logout: vi.fn(),
    user: null,
    loading: false,
  }),
}));

// Mock useAuth hook
vi.mock('../../hooks/useAuth', () => ({
  useAuthActions: vi.fn(() => ({
    register: vi.fn(),
    login: vi.fn(),
    updateProfile: vi.fn(),
    logout: vi.fn(),
    loading: false,
    error: null,
  })),
}));

const renderWithProviders = (component: React.ReactNode) => {
  return render(
    <AuthProvider>
      {component}
    </AuthProvider>
  );
};

const onSwitchToLogin = vi.fn();

describe('Register Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockClear();
  });

  describe('Render', () => {
    it('should render registration form with all required fields', () => {
      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      expect(screen.getByRole('heading', { name: 'Register' })).toBeInTheDocument();
      expect(screen.getByLabelText(/^Email\s+\*\s*$/)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Confirm Password\s+\*\s*$/)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Name \(optional\)$/)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Surname \(optional\)$/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /register/i })).toBeInTheDocument();
      expect(screen.getByText(/already have an account?/i)).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should show error when passwords do not match', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
      const registerButton = screen.getByRole('button', { name: /register/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'differentpassword');
      await user.click(registerButton);

      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });

    it('should show error when password is too short', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
      const registerButton = screen.getByRole('button', { name: /register/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, '123');
      await user.type(confirmPasswordInput, '123');
      await user.click(registerButton);

      expect(screen.getByText("Password must be at least 6 characters")).toBeInTheDocument();
    });

    it('should not submit with empty required fields', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.fn();

      const mockUseAuthActions = vi.mocked(useAuthActions);
      mockUseAuthActions.mockReturnValue({
        register: mockRegister,
        login: vi.fn(),
        updateProfile: vi.fn(),
        logout: vi.fn(),
        loading: false,
        error: null,
      });

      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const registerButton = screen.getByRole('button', { name: /register/i });
      await user.click(registerButton);

      // Verify register was not called due to HTML5 validation
      expect(mockRegister).not.toHaveBeenCalled();

      // Verify required fields are marked as required
      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      expect(emailInput).toBeRequired();
      expect(passwordInput).toBeRequired();
      expect(emailInput).toBeInvalid(); // HTML5 validation state
    });
  });

  describe('API Integration', () => {
      it('should call register API with correct data when form is submitted', async () => {
        const user = userEvent.setup();
        const mockRegister = vi.fn().mockResolvedValue({ user: { id: 1, email: 'test@example.com' } });

        const mockUseAuthActions = vi.mocked(useAuthActions);
        mockUseAuthActions.mockReturnValue({
          register: mockRegister,
          login: vi.fn(),
          updateProfile: vi.fn(),
          logout: vi.fn(),
          loading: false,
          error: null,
        });

        renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

        const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
        const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
        const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
        const registerButton = screen.getByRole('button', { name: /register/i });

        await user.type(emailInput, 'test@example.com');
        await user.type(passwordInput, 'password123');
        await user.type(confirmPasswordInput, 'password123');
        await user.click(registerButton);

        await waitFor(() => {
          expect(mockRegister).toHaveBeenCalledWith({
            email: 'test@example.com',
            password: 'password123',
            name: undefined,
            surname: undefined,
          });
        });
      });

      it('should include optional name and surname if provided', async () => {
        const user = userEvent.setup();
        const mockRegister = vi.fn().mockResolvedValue({ user: { id: 1, email: 'test@example.com' } });

        const mockUseAuthActions = vi.mocked(useAuthActions);
        mockUseAuthActions.mockReturnValue({
          register: mockRegister,
          login: vi.fn(),
          updateProfile: vi.fn(),
          logout: vi.fn(),
          loading: false,
          error: null,
        });

        renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

        const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
        const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
        const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
        const nameInput = screen.getByLabelText(/^Name \(optional\)$/);
        const surnameInput = screen.getByLabelText(/^Surname \(optional\)$/);
        const registerButton = screen.getByRole('button', { name: /register/i });

        await user.type(emailInput, 'test@example.com');
        await user.type(passwordInput, 'password123');
        await user.type(confirmPasswordInput, 'password123');
        await user.type(nameInput, 'John');
        await user.type(surnameInput, 'Doe');
        await user.click(registerButton);

        await waitFor(() => {
          expect(mockRegister).toHaveBeenCalledWith({
            email: 'test@example.com',
            password: 'password123',
            name: 'John',
            surname: 'Doe',
          });
        });
      });

      it('should handle registration loading state', async () => {
        const mockRegister = vi.fn().mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));

        const mockUseAuthActions = vi.mocked(useAuthActions);
        mockUseAuthActions.mockReturnValue({
          register: mockRegister,
          login: vi.fn(),
          updateProfile: vi.fn(),
          logout: vi.fn(),
          loading: true,
          error: null,
        });

        renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

        // When loading is true, button should show "Registering..." text
        expect(screen.getByText("Registering...")).toBeInTheDocument();
        const registerButton = screen.getByRole('button', { name: /registering/i });
        expect(registerButton).toBeDisabled();
      });
    });

  describe('Error Handling', () => {
    it('should display error message when registration fails', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.fn().mockRejectedValue(new Error("Registration failed"));

      const mockUseAuthActions = vi.mocked(useAuthActions);
      mockUseAuthActions.mockReturnValue({
        register: mockRegister,
        login: vi.fn(),
        updateProfile: vi.fn(),
        logout: vi.fn(),
        loading: false,
        error: null,
      });

      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
      const registerButton = screen.getByRole('button', { name: /register/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password123');
      await user.click(registerButton);

      await waitFor(() => {
        expect(screen.getByText("Registration failed")).toBeInTheDocument();
      });
    });
  });

  describe('Form Requirements', () => {
    it('should mark required fields appropriately', () => {
      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/) as HTMLInputElement;
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/) as HTMLInputElement;
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/) as HTMLInputElement;

      expect(emailInput).toBeRequired();
      expect(passwordInput).toBeRequired();
      expect(confirmPasswordInput).toBeRequired();
    });
  });

  describe('Switch to Login', () => {
    it('should call onSwitchToLogin when clicking login link', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const loginButton = screen.getByText(/already have an account?/i).closest('button');
      expect(loginButton).toBeInTheDocument();

      if (loginButton) {
        await user.click(loginButton);
        expect(onSwitchToLogin).toHaveBeenCalled();
      }
    });
  });

  describe('Edge Cases', () => {
    it('should register with only required fields (email and password)', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.fn().mockResolvedValue({
        user: { id: 1, email: 'minimal@example.com' }
      });

      const mockUseAuthActions = vi.mocked(useAuthActions);
      mockUseAuthActions.mockReturnValue({
        register: mockRegister,
        login: vi.fn(),
        updateProfile: vi.fn(),
        logout: vi.fn(),
        loading: false,
        error: null,
      });

      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
      const registerButton = screen.getByRole('button', { name: /register/i });

      await user.type(emailInput, 'minimal@example.com');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password123');
      await user.click(registerButton);

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith({
          email: 'minimal@example.com',
          password: 'password123',
          name: undefined,
          surname: undefined,
        });
      });
    });

    it('should clear error when user corrects input', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
      const registerButton = screen.getByRole('button', { name: /register/i });

      // First trigger password mismatch error
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'different');
      await user.click(registerButton);

      expect(screen.getByText('Passwords do not match')).toBeInTheDocument();

      // Now correct the password - trigger validation again
      await user.clear(confirmPasswordInput);
      await user.type(confirmPasswordInput, 'password123');

      // Re-click to trigger validation, error should clear
      await user.click(registerButton);

      // Error should no longer appear
      expect(screen.queryByText('Passwords do not match')).not.toBeInTheDocument();
    });

    it('should validate email format (server-side validation)', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.fn().mockRejectedValue(new Error('Invalid email format'));

      const mockUseAuthActions = vi.mocked(useAuthActions);
      mockUseAuthActions.mockReturnValue({
        register: mockRegister,
        login: vi.fn(),
        updateProfile: vi.fn(),
        logout: vi.fn(),
        loading: false,
        error: null,
      });

      renderWithProviders(<Register onSwitchToLogin={onSwitchToLogin} />);

      const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
      const passwordInput = screen.getByLabelText(/^Password \(min\. 6 characters\)\s+\*\s*$/);
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password\s+\*\s*$/);
      const registerButton = screen.getByRole('button', { name: /register/i });

      await user.type(emailInput, 'invalid-email');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password123');
      await user.click(registerButton);

      // Component should show error from register function
      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalled();
      });

      // Error message appears
      expect(screen.getByText(/Invalid email format/)).toBeInTheDocument();
    });
  });
});
