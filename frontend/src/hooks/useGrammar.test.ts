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

  it('should search grammar cheatsheets', async () => {
    const mockResults = [
      {
        title: 'Adjective comparison rules',
        url: 'http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation',
        path: 'adjectives/komparation.md',
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ results: mockResults }),
      });

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.searchGrammar('adjective comparison');
    });

    expect(mockFetch).toHaveBeenLastCalledWith(
      '/api/grammar/search?query=adjective+comparison&top_k=3'
    );
    expect(result.current.searchResults).toEqual(mockResults);
    expect(result.current.searchError).toBeNull();
  });

  it('should not call grammar search for empty queries', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    });

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.searchGrammar('   ');
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(result.current.searchResults).toEqual([]);
    expect(result.current.searchError).toBeNull();
  });

  it('should clear grammar search state', async () => {
    const mockResults = [
      {
        title: 'Verb forms',
        url: 'http://localhost:5173/?view=grammar&cheatsheet=verbs/verb-forms',
        path: 'verbs/verb-forms.md',
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ results: mockResults }),
      });

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.searchGrammar('verbs');
      result.current.clearSearch();
    });

    expect(result.current.searchResults).toEqual([]);
    expect(result.current.searchError).toBeNull();
    expect(result.current.searchLoading).toBe(false);
  });

  it('should handle grammar search errors', async () => {
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
      await result.current.searchGrammar('verbs');
    });

    expect(result.current.searchError).toBe('Network error');
    expect(result.current.searchResults).toEqual([]);
  });

  it('should ignore stale grammar search responses', async () => {
    const latestResults = [
      {
        title: 'Second query result',
        url: 'http://localhost:5173/?view=grammar&cheatsheet=verbs/latest',
        path: 'verbs/latest.md',
      },
    ];
    const staleResults = [
      {
        title: 'First query result',
        url: 'http://localhost:5173/?view=grammar&cheatsheet=verbs/stale',
        path: 'verbs/stale.md',
      },
    ];

    let resolveFirstSearch: ((value: { ok: boolean; json: () => Promise<{ results: typeof staleResults }> }) => void) | null = null;
    let resolveSecondSearch: ((value: { ok: boolean; json: () => Promise<{ results: typeof latestResults }> }) => void) | null = null;

    const firstSearchPromise = new Promise<{ ok: boolean; json: () => Promise<{ results: typeof staleResults }> }>(
      (resolve) => {
        resolveFirstSearch = resolve;
      }
    );
    const secondSearchPromise = new Promise<{ ok: boolean; json: () => Promise<{ results: typeof latestResults }> }>(
      (resolve) => {
        resolveSecondSearch = resolve;
      }
    );

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockImplementationOnce(() => firstSearchPromise)
      .mockImplementationOnce(() => secondSearchPromise);

    const { result } = renderHook(() => useGrammar());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    act(() => {
      void result.current.searchGrammar('first query');
      void result.current.searchGrammar('second query');
    });

    await act(async () => {
      resolveSecondSearch?.({
        ok: true,
        json: () => Promise.resolve({ results: latestResults }),
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.searchResults).toEqual(latestResults);
    });

    await act(async () => {
      resolveFirstSearch?.({
        ok: true,
        json: () => Promise.resolve({ results: staleResults }),
      });
      await Promise.resolve();
    });

    expect(result.current.searchResults).toEqual(latestResults);
    expect(result.current.searchError).toBeNull();
  });
});
