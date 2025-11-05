import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useApi } from './api';
import { AuthProvider } from '../context/AuthContext';

/// <reference types="vitest/globals" />

// Mock fetch
(globalThis as any).fetch = vi.fn();

describe('useApi', () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('injects Authorization header when token exists', async () => {
    const mockResponse = { data: 'test' };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    // Set up auth context with token
    const { result } = renderHook(() => useApi(), {
      wrapper: ({ children }) => {
        const TestWrapper = () => (
          <AuthProvider>
            {/* Mock authenticated state */}
            {(() => {
              // Simulate login
              const authContext = (window as any).__authContext;
              if (authContext) {
                authContext.login('test-token', {
                  id: 1,
                  email: 'test@example.com',
                  name: 'Test',
                  surname: 'User',
                  timezone: 'UTC',
                  pages_recognised_count: 0
                });
              }
              return children;
            })()}
          </AuthProvider>
        );
        return <TestWrapper>{children}</TestWrapper>;
      },
    });

    await result.current('/test-endpoint');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/test-endpoint',
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
    (global.fetch as any).mockResolvedValueOnce({
      status: 401,
      ok: false,
      json: () => Promise.resolve({ detail: 'Unauthorized' }),
    });

    // Mock the auth context
    const { result } = renderHook(() => useApi(), { wrapper });

    // Mock the logout function in context
    const mockUseAuth = vi.fn(() => ({
      token: 'test-token',
      logout: mockLogout,
    }));

    // We need to mock the useAuth hook for this test
    vi.mock('../context/AuthContext', () => ({
      useAuth: mockUseAuth,
    }));

    await expect(result.current('/test-endpoint')).rejects.toThrow(
      'Authentication required. Please log in again.'
    );

    expect(mockLogout).toHaveBeenCalled();
  });

  it('makes successful API calls', async () => {
    const mockResponse = { data: 'success' };
    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    const response = await result.current('/test-endpoint');

    expect(response).toEqual(mockResponse);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/test-endpoint',
      expect.any(Object)
    );
  });

  it('handles error responses', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Bad Request' }),
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    await expect(result.current('/test-endpoint')).rejects.toThrow('Bad Request');
  });

  it('handles network errors', async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useApi(), { wrapper });

    await expect(result.current('/test-endpoint')).rejects.toThrow('Network error');
  });

  it('retrieves token from AuthContext', async () => {
    const mockResponse = { data: 'test' };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    // Mock useAuth to return a token
    const mockUseAuth = vi.fn(() => ({
      token: 'mock-token-from-context',
      logout: vi.fn(),
    }));

    vi.mock('../context/AuthContext', () => ({
      useAuth: mockUseAuth,
    }));

    const { result } = renderHook(() => useApi(), { wrapper });

    await result.current('/test-endpoint');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/test-endpoint',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer mock-token-from-context',
        }),
      })
    );
  });

  it('sends POST requests with body', async () => {
    const mockResponse = { success: true };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    const testBody = { email: 'test@example.com', password: 'password123' };
    await result.current('/auth/token', {
      method: 'POST',
      body: testBody,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/token',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(testBody),
      })
    );
  });

  it('uses default GET method when not specified', async () => {
    const mockResponse = { data: 'test' };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useApi(), { wrapper });

    await result.current('/test-endpoint');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/test-endpoint',
      expect.objectContaining({
        method: 'GET',
      })
    );
  });
});
