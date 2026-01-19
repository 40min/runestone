import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatImageUpload } from './useChatImageUpload';
import { AuthProvider } from '../context/AuthContext';
import React from 'react';

// Mock the API
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock URL.createObjectURL and crypto.randomUUID
global.URL.createObjectURL = vi.fn(() => 'blob:test-image-url');
global.crypto.randomUUID = vi.fn(() => 'test-uuid-1');

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn((key) => {
    if (key === 'runestone_token') return 'test-token';
    if (key === 'runestone_user_data') {
      return JSON.stringify({
        id: '1',
        email: 'test@example.com',
        username: 'testuser',
      });
    }
    return null;
  }),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// Wrapper component to provide AuthContext
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

describe('useChatImageUpload', () => {
  const resetLocalStorage = () => {
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'runestone_token') return 'test-token';
      if (key === 'runestone_user_data') {
        return JSON.stringify({
          id: '1',
          email: 'test@example.com',
          username: 'testuser',
        });
      }
      return null;
    });
  };

  beforeEach(() => {
    mockFetch.mockClear();
    vi.clearAllMocks();
    resetLocalStorage();
  });

  it('uploads image successfully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Translation result' }),
    });

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    const file = new File(['test'], 'test.png', { type: 'image/png' });

    let translationMessage: string | null = null;
    await act(async () => {
      translationMessage = await result.current.uploadImage(file);
    });

    expect(translationMessage).toBe('Translation result');
    expect(result.current.uploadedImages).toHaveLength(1);
    expect(result.current.uploadedImages[0].url).toBe('blob:test-image-url');
    expect(result.current.error).toBeNull();
    expect(result.current.isUploading).toBe(false);
  });

  it('enforces FIFO behavior with max 3 images', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: 'Translation' }),
    });

    // Mock crypto.randomUUID to return different IDs
    let uuidCounter = 0;
    vi.mocked(global.crypto.randomUUID).mockImplementation(() => `uuid-${++uuidCounter}`);

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    // Upload 4 images
    for (let i = 1; i <= 4; i++) {
      const file = new File(['test'], `test${i}.png`, { type: 'image/png' });
      await act(async () => {
        await result.current.uploadImage(file);
      });
    }

    // Should only keep the last 3
    expect(result.current.uploadedImages).toHaveLength(3);
    expect(result.current.uploadedImages[0].id).toBe('uuid-2');
    expect(result.current.uploadedImages[1].id).toBe('uuid-3');
    expect(result.current.uploadedImages[2].id).toBe('uuid-4');
  });

  it('handles upload errors', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    const file = new File(['test'], 'test.png', { type: 'image/png' });

    let translationMessage: string | null = null;
    await act(async () => {
      translationMessage = await result.current.uploadImage(file);
    });

    expect(translationMessage).toBeNull();
    expect(result.current.error).toBe('Network error');
    expect(result.current.uploadedImages).toHaveLength(0);
    expect(result.current.isUploading).toBe(false);
  });

  it('requires authentication', async () => {
    // Mock no token
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'runestone_user_data') {
        return JSON.stringify({
          id: '1',
          email: 'test@example.com',
          username: 'testuser',
        });
      }
      return null; // No token
    });

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    const file = new File(['test'], 'test.png', { type: 'image/png' });

    let translationMessage: string | null = null;
    await act(async () => {
      translationMessage = await result.current.uploadImage(file);
    });

    expect(translationMessage).toBeNull();
    expect(result.current.error).toBe('Authentication required');
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('clears images', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Translation' }),
    });

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    // Upload an image
    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await act(async () => {
      await result.current.uploadImage(file);
    });

    expect(result.current.uploadedImages).toHaveLength(1);

    // Clear images
    act(() => {
      result.current.clearImages();
    });

    expect(result.current.uploadedImages).toHaveLength(0);
  });

  it('clears error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Test error'));

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await act(async () => {
      await result.current.uploadImage(file);
    });

    expect(result.current.error).toBe('Test error');

    // Clear error
    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it('manages isUploading state correctly', async () => {
    let resolvePromise: (value: Response | PromiseLike<Response>) => void;
    mockFetch.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
    );

    const { result } = renderHook(() => useChatImageUpload(), { wrapper });

    expect(result.current.isUploading).toBe(false);

    const file = new File(['test'], 'test.png', { type: 'image/png' });

    // Start upload
    let uploadResultPromise: Promise<string | null>;
    act(() => {
      uploadResultPromise = result.current.uploadImage(file);
    });

    // Should be uploading
    await waitFor(() => {
      expect(result.current.isUploading).toBe(true);
    });

    // Resolve the upload
    await act(async () => {
      resolvePromise!({
        ok: true,
        json: async () => ({ message: 'Translation' }),
      } as Response);
    });

    await uploadResultPromise!;

    // Should no longer be uploading
    expect(result.current.isUploading).toBe(false);
  });
});
