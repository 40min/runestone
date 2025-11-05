import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { useAuthActions } from './useAuth';
import { AuthProvider } from '../context/AuthContext';

/// <reference types="vitest/globals" />

// Mock fetch
(globalThis as any).fetch = vi.fn();

describe('useAuthActions', () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
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

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.login({ email: 'test@example.com', password: 'password123' });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/token',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
      })
    );

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/users/me',
      expect.any(Object)
    );

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it('handles login failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.login({ email: 'test@example.com', password: 'wrong' })).rejects.toThrow('Invalid credentials');

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Invalid credentials');
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

    (globalThis.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.register({
      email: 'test@example.com',
      password: 'password123',
      name: 'Test',
      surname: 'User'
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/register',
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
      'http://localhost:8000/auth/token',
      expect.any(Object)
    );

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it('handles registration failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Email already exists' }),
    });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.register({
      email: 'existing@example.com',
      password: 'password123'
    })).rejects.toThrow('Email already exists');

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Email already exists');
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

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUpdateResponse),
    });

    // Mock localStorage
    const mockLocalStorage = {
      getItem: vi.fn(() => 'existing-token'),
      setItem: vi.fn(),
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
      'http://localhost:8000/users/me',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          name: 'Updated',
          surname: 'Name',
          timezone: 'EST'
        }),
      })
    );

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it('handles profile update failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Update failed' }),
    });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.updateProfile({
      name: 'New Name'
    })).rejects.toThrow('Update failed');

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Update failed');
  });

  it('sets loading state during operations', async () => {
    (global.fetch as any).mockImplementation(() =>
      new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'token' }),
      }), 100))
    );

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    const loginPromise = result.current.login({ email: 'test@example.com', password: 'password123' });

    expect(result.current.loading).toBe(true);

    await loginPromise;

    expect(result.current.loading).toBe(false);
  });

  it('resets error state on new operations', async () => {
    // First operation fails
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'First error' }),
    });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await expect(result.current.login({ email: 'test@example.com', password: 'wrong' })).rejects.toThrow();

    expect(result.current.error).toBe('First error');

    // Second operation should reset error
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ access_token: 'token' }),
    });

    await result.current.login({ email: 'test@example.com', password: 'correct' });

    expect(result.current.error).toBe(null);
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

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.register({
      email: 'new@example.com',
      password: 'password123'
    });

    // Verify login was called with registration credentials
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/token',
      expect.objectContaining({
        body: JSON.stringify({
          email: 'new@example.com',
          password: 'password123'
        }),
      })
    );
  });
});
