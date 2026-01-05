import React from 'react';
import { renderHook } from '@testing-library/react';
import { vi } from 'vitest';
import { useApi } from './api';
import { AuthProvider } from '../context/AuthContext';
import * as AuthContext from '../context/AuthContext';

/// <reference types="vitest/globals" />

// Mock config
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
vi.stubGlobal('fetch', vi.fn());

// Mock useAuth hook
vi.mock('../context/AuthContext', async () => {
  const actual = await vi.importActual('../context/AuthContext');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

describe('useApi', () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock to complete default implementation
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      token: null,
      userData: null,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: () => false,
    });
  });

  it('injects Authorization header when token exists', async () => {
    const mockResponse = { data: 'test' };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    // Set up auth context with token
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      token: 'test-token',
      userData: null,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: () => true,
    });

    const { result } = renderHook(() => useApi(), {
      wrapper: ({ children }) => (
        <AuthProvider>
          {children}
        </AuthProvider>
      ),
    });

    await result.current('/test-endpoint');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/test-endpoint',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer test-token',
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  it('handles 401 response by calling logout', async () => {
    const mockLogout = vi.fn();
    vi.mocked(global.fetch).mockResolvedValueOnce({
      status: 401,
      ok: false,
      json: () => Promise.resolve({ detail: 'Unauthorized' }),
    } as Response);

    // Mock the auth context
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      token: 'test-token',
      userData: null,
      login: vi.fn(),
      logout: mockLogout,
      isAuthenticated: () => true,
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    await expect(result.current('/test-endpoint')).rejects.toThrow(
      'Unauthorized'
    );

    expect(mockLogout).toHaveBeenCalled();
  });

  it('makes successful API calls', async () => {
    const mockResponse = { data: 'success' };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    const response = await result.current('/test-endpoint');

    expect(response).toEqual(mockResponse);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/test-endpoint',
      expect.any(Object)
    );
  });

  it('handles error responses', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Bad Request' }),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    await expect(result.current('/test-endpoint')).rejects.toThrow('Bad Request');
  });

  it('handles network errors', async () => {
    vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useApi(), { wrapper });

    await expect(result.current('/test-endpoint')).rejects.toThrow('Network error');
  });

  it('retrieves token from AuthContext', async () => {
    const mockResponse = { data: 'test' };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    // Mock useAuth to return a token
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      token: 'mock-token-from-context',
      userData: null,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: () => true,
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    await result.current('/test-endpoint');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/test-endpoint',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer mock-token-from-context',
        }),
      })
    );
  });

  it('sends POST requests with body', async () => {
    const mockResponse = { success: true };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    const testBody = { email: 'test@example.com', password: 'password123' };
    await result.current('/api/auth', {
      method: 'POST',
      body: testBody,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/auth',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(testBody),
      })
    );
  });

  it('uses default GET method when not specified', async () => {
    const mockResponse = { data: 'test' };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    await result.current('/test-endpoint');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/test-endpoint',
      expect.objectContaining({
        method: 'GET',
      })
    );
  });

  it('preserves custom headers when provided', async () => {
    const mockResponse = { data: 'test' };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    vi.mocked(AuthContext.useAuth).mockReturnValue({
      token: 'test-token',
      userData: null,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: () => true,
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    await result.current('/test-endpoint', {
      headers: {
        'X-Custom-Header': 'custom-value',
      },
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/test-endpoint',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer test-token',
          'Content-Type': 'application/json',
          'X-Custom-Header': 'custom-value',
        }),
      })
    );
  });

  it('handles PUT requests', async () => {
    const mockResponse = { success: true };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    const updateData = { name: 'Updated' };
    await result.current('/users/me', {
      method: 'PUT',
      body: updateData,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/users/me',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(updateData),
      })
    );
  });

  it('handles DELETE requests', async () => {
    const mockResponse = { success: true };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    await result.current('/users/1', {
      method: 'DELETE',
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/users/1',
      expect.objectContaining({
        method: 'DELETE',
      })
    );
  });

  it('handles PATCH requests', async () => {
    const mockResponse = { success: true };
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    const patchData = { status: 'active' };
    await result.current('/users/1', {
      method: 'PATCH',
      body: patchData,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/users/1',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify(patchData),
      })
    );
  });

  it('handles responses without JSON body (204 No Content)', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error('No content')),
    } as Response);

    const { result } = renderHook(() => useApi(), { wrapper });

    // Should return null for 204 responses instead of throwing
    const response = await result.current('/test-endpoint');
    expect(response).toBeNull();
  });
});
