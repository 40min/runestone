import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useAuthActions } from './useAuth';
import { AuthProvider } from '../context/AuthContext';

/// <reference types="vitest/globals" />

// Mock config
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
vi.stubGlobal('fetch', vi.fn());

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

describe('useAuthActions', () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset localStorage mock to return null by default
    mockLocalStorage.getItem.mockReturnValue(null);
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

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.login({ email: 'test@example.com', password: 'password123' });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/auth/token',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
      })
    );

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/users/me',
      expect.any(Object)
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it('handles login failure', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.login({ email: 'test@example.com', password: 'wrong' })).rejects.toThrow('Invalid credentials');

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe('Invalid credentials');
    });
  });

  it('handles successful registration', async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: 'test-token' };
    const mockUserResponse = {
      id: 1,
      email: 'test@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 0
    };

    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.register({
      email: 'test@example.com',
      password: 'password123',
      name: 'Test',
      surname: 'User'
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/auth/register',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          email: 'test@example.com',
          password: 'password123',
          name: 'Test',
          surname: 'User'
        }),
      })
    );

    // Should automatically login after registration
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/auth/token',
      expect.any(Object)
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it('handles registration failure', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Email already exists' }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.register({
      email: 'existing@example.com',
      password: 'password123'
    })).rejects.toThrow('Email already exists');

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe('Email already exists');
    });
  });

  it('handles successful profile update', async () => {
    const mockUpdateResponse = {
      id: 1,
      email: 'test@example.com',
      name: 'Updated',
      surname: 'Name',
      timezone: 'EST',
      pages_recognised_count: 5
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUpdateResponse),
    } as Response);

    // Mock localStorage
    const mockLocalStorage = {
      getItem: vi.fn(() => 'existing-token'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
    });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.updateProfile({
      name: 'Updated',
      surname: 'Name',
      timezone: 'EST'
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/users/me',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          name: 'Updated',
          surname: 'Name',
          timezone: 'EST'
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it('handles profile update failure', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Update failed' }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.updateProfile({
      name: 'New Name'
    })).rejects.toThrow('Update failed');

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe('Update failed');
    });
  });

  it('sets loading state during operations', async () => {
    vi.mocked(global.fetch).mockImplementation(() =>
      new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'token' }),
      } as Response), 100))
    );

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    const loginPromise = result.current.login({ email: 'test@example.com', password: 'password123' });

    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });

    await loginPromise;

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it('resets error state on new operations', async () => {
    // First operation fails
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'First error' }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.login({ email: 'test@example.com', password: 'wrong' })).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.error).toBe('First error');
    });

    // Second operation should reset error
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ access_token: 'token' }),
    } as Response);

    await result.current.login({ email: 'test@example.com', password: 'correct' });

    await waitFor(() => {
      expect(result.current.error).toBe(null);
    });
  });

  it('auto-logs in after successful registration', async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: 'registration-token' };
    const mockUserResponse = {
      id: 1,
      email: 'new@example.com',
      name: 'New',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 0
    };

    vi.mocked(global.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.register({
      email: 'new@example.com',
      password: 'password123'
    });

    // Verify login was called with registration credentials
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/auth/token',
      expect.objectContaining({
        body: JSON.stringify({
          email: 'new@example.com',
          password: 'password123'
        }),
      })
    );
  });
});
