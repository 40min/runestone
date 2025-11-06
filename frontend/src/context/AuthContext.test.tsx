import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

describe('AuthContext', () => {
  let consoleSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockLocalStorage.getItem.mockClear();
    mockLocalStorage.setItem.mockClear();
    mockLocalStorage.removeItem.mockClear();
  });

  afterEach(() => {
    // Clean up console spy if it exists
    if (consoleSpy) {
      consoleSpy.mockRestore();
      consoleSpy = null;
    }
  });

  const TestComponent = () => {
    const { token, userData, login, logout, isAuthenticated } = useAuth();
    return (
      <div>
        <div data-testid="token">{token || 'null'}</div>
        <div data-testid="userData">{userData ? JSON.stringify(userData) : 'null'}</div>
        <div data-testid="isAuthenticated">{isAuthenticated().toString()}</div>
        <button onClick={() => login('test-token', { id: 1, email: 'test@example.com', name: 'Test', surname: 'User', timezone: 'UTC', pages_recognised_count: 0 })}>
          Login
        </button>
        <button onClick={logout}>Logout</button>
      </div>
    );
  };

  it('provides initial null state', () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('token')).toHaveTextContent('null');
    expect(screen.getByTestId('userData')).toHaveTextContent('null');
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
  });

  it('loads token and userData from localStorage on mount', () => {
    const mockUserData = { id: 1, email: 'test@example.com', name: 'Test', surname: 'User', timezone: 'UTC', pages_recognised_count: 5 };
    mockLocalStorage.getItem.mockImplementation((key: string) => {
      if (key === 'runestone_token') return 'stored-token';
      if (key === 'runestone_user_data') return JSON.stringify(mockUserData);
      return null;
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('token')).toHaveTextContent('stored-token');
    expect(screen.getByTestId('userData')).toHaveTextContent(JSON.stringify(mockUserData));
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
  });

  it('handles malformed localStorage userData gracefully', () => {
    mockLocalStorage.getItem.mockImplementation((key: string) => {
      if (key === 'runestone_token') return 'stored-token';
      if (key === 'runestone_user_data') return 'invalid-json';
      return null;
    });

    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('token')).toHaveTextContent('stored-token');
    expect(screen.getByTestId('userData')).toHaveTextContent('null');
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
    expect(consoleSpy).toHaveBeenCalledWith('Failed to parse stored user data:', expect.any(Error));
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('runestone_user_data');
  });

  it('updates state on login', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    fireEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('test-token');
      expect(screen.getByTestId('userData')).toHaveTextContent(JSON.stringify({
        id: 1,
        email: 'test@example.com',
        name: 'Test',
        surname: 'User',
        timezone: 'UTC',
        pages_recognised_count: 0
      }));
      expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
    });

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('runestone_token', 'test-token');
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('runestone_user_data', JSON.stringify({
      id: 1,
      email: 'test@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 0
    }));
  });

  it('clears state on logout', async () => {
    const mockUserData = { id: 1, email: 'test@example.com', name: 'Test', surname: 'User', timezone: 'UTC', pages_recognised_count: 5 };
    mockLocalStorage.getItem.mockImplementation((key: string) => {
      if (key === 'runestone_token') return 'stored-token';
      if (key === 'runestone_user_data') return JSON.stringify(mockUserData);
      return null;
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const logoutButton = screen.getByText('Logout');
    fireEvent.click(logoutButton);

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('null');
      expect(screen.getByTestId('userData')).toHaveTextContent('null');
      expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
    });

    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('runestone_token');
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('runestone_user_data');
  });

  it('isAuthenticated returns false when token is null', () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
  });

  it('isAuthenticated returns false when userData is null', () => {
    mockLocalStorage.getItem.mockImplementation((key: string) => {
      if (key === 'runestone_token') return 'stored-token';
      return null;
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
  });

  it('isAuthenticated returns true when both token and userData exist', () => {
    const mockUserData = { id: 1, email: 'test@example.com', name: 'Test', surname: 'User', timezone: 'UTC', pages_recognised_count: 5 };
    mockLocalStorage.getItem.mockImplementation((key: string) => {
      if (key === 'runestone_token') return 'stored-token';
      if (key === 'runestone_user_data') return JSON.stringify(mockUserData);
      return null;
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
  });

  it('throws error when useAuth is used outside AuthProvider', () => {
    const TestComponentNoProvider = () => {
      useAuth();
      return <div>Test</div>;
    };

    expect(() => render(<TestComponentNoProvider />)).toThrow(
      'useAuth must be used within an AuthProvider'
    );
  });

  it('updates userData after login', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    fireEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
    });

    // Verify userData was updated
    const userData = JSON.parse(screen.getByTestId('userData').textContent || '{}');
    expect(userData).toEqual({
      id: 1,
      email: 'test@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 0
    });
  });

  it('handles concurrent login and logout gracefully', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    const logoutButton = screen.getByText('Logout');

    // Trigger login and logout almost simultaneously
    fireEvent.click(loginButton);
    fireEvent.click(logoutButton);

    await waitFor(() => {
      // Should end up logged out
      expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
      expect(screen.getByTestId('token')).toHaveTextContent('null');
      expect(screen.getByTestId('userData')).toHaveTextContent('null');
    });
  });

  it('persists authentication state across re-renders', () => {
    const mockUserData = {
      id: 1,
      email: 'test@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 5
    };

    mockLocalStorage.getItem.mockImplementation((key: string) => {
      if (key === 'runestone_token') return 'stored-token';
      if (key === 'runestone_user_data') return JSON.stringify(mockUserData);
      return null;
    });

    const { rerender } = render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');

    // Re-render should maintain state
    rerender(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
    expect(screen.getByTestId('token')).toHaveTextContent('stored-token');
  });
});
