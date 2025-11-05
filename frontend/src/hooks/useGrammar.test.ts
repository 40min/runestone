import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import useGrammar from './useGrammar';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('useGrammar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch cheatsheets on mount', async () => {
    const mockCheatsheets = [
      { filename: 'test1.md', title: 'Test 1', category: 'General' },
      { filename: 'test2.md', title: 'Test 2', category: 'Verbs' },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCheatsheets),
    });

    const { result } = renderHook(() => useGrammar());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.cheatsheets).toEqual(mockCheatsheets);
    expect(result.current.error).toBeNull();
  });

  it('should handle fetch cheatsheets error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.cheatsheets).toEqual([]);
  });

  it('should fetch cheatsheet content', async () => {
    const mockContent = { content: '# Test Content' };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockContent),
      });

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.fetchCheatsheetContent('test.md');
    });

    await waitFor(() => {
      expect(result.current.selectedCheatsheet).toEqual(mockContent);
    });

    expect(result.current.error).toBeNull();
  });

  it('should handle fetch cheatsheet content error', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.fetchCheatsheetContent('test.md');
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Network error');
    });

    expect(result.current.selectedCheatsheet).toBeNull();
  });
});
