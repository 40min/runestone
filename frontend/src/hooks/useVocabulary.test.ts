import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import useVocabulary, { useRecentVocabulary, useVocabularyStats, improveVocabularyItem } from './useVocabulary';
import { VOCABULARY_IMPROVEMENT_MODES } from '../constants';
import { ApiClientOptions } from '../utils/api';

// Mock config
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

// Mock AuthContext
vi.mock('../context/AuthContext', () => {
  const mockLogout = vi.fn();
  return {
    useAuth: () => ({
      token: null,
      userData: null,
      login: vi.fn(),
      logout: mockLogout,
      isAuthenticated: () => false,
    }),
    AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  };
});

describe('useVocabulary', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch vocabulary successfully', async () => {
    const mockVocabularyResponse = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        created_at: '2023-10-27T10:00:00Z',
      },
      {
        id: 2,
        user_id: 1,
        word_phrase: 'bra',
        translation: 'good',
        example_phrase: 'Jag mår bra idag.',
        created_at: '2023-10-27T10:05:00Z',
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockVocabularyResponse),
    });

    const { result } = renderHook(() => useVocabulary());

    await waitFor(() => {
      expect(result.current.vocabulary).toEqual(mockVocabularyResponse);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });

  it('should handle fetch error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: 'Failed to fetch vocabulary: HTTP 500' }),
    });

    const { result } = renderHook(() => useVocabulary());

    await waitFor(() => {
      expect(result.current.error).toBe('Failed to fetch vocabulary: HTTP 500');
      expect(result.current.loading).toBe(false);
      expect(result.current.vocabulary).toEqual([]);
    });
  });

  it('should handle network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useVocabulary());

    await waitFor(() => {
      expect(result.current.error).toBe('Network error');
      expect(result.current.loading).toBe(false);
      expect(result.current.vocabulary).toEqual([]);
    });
  });

  it('should refetch vocabulary when refetch is called', async () => {
    const mockVocabularyResponse = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        created_at: '2023-10-27T10:00:00Z',
      },
    ];

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockVocabularyResponse),
    });

    const { result } = renderHook(() => useVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    // Should have called fetch twice
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});

describe('useRecentVocabulary', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch recent vocabulary with limit=20 when no search query', async () => {
    const mockVocabularyResponse = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockVocabularyResponse),
    });

    const { result } = renderHook(() => useRecentVocabulary());

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse);
      expect(result.current.loading).toBe(false);
      expect(result.current.hasMore).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary?limit=20&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });

  it('should load more recent vocabulary with the next offset and append results', async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      id: index + 1,
      user_id: 1,
      word_phrase: `word-${index + 1}`,
      translation: `translation-${index + 1}`,
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    }));
    const secondPage = [
      {
        id: 21,
        user_id: 1,
        word_phrase: 'word-21',
        translation: 'translation-21',
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
      {
        id: 22,
        user_id: 1,
        word_phrase: 'word-22',
        translation: 'translation-22',
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(firstPage),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(secondPage),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(firstPage);
      expect(result.current.hasMore).toBe(true);
    });

    await act(async () => {
      await result.current.loadMore();
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/vocabulary?limit=20&offset=20',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
    expect(result.current.recentVocabulary).toEqual([...firstPage, ...secondPage]);
    expect(result.current.hasMore).toBe(false);
  });

  it('should avoid appending duplicate items when loading more', async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      id: index + 1,
      user_id: 1,
      word_phrase: `word-${index + 1}`,
      translation: `translation-${index + 1}`,
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    }));
    const duplicatePage = [
      firstPage[19],
      {
        id: 21,
        user_id: 1,
        word_phrase: 'word-21',
        translation: 'translation-21',
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(firstPage),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(duplicatePage),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    await waitFor(() => {
      expect(result.current.hasMore).toBe(true);
    });

    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.recentVocabulary).toHaveLength(21);
    expect(result.current.recentVocabulary.at(-1)?.word_phrase).toBe('word-21');
  });

  it('should refetch the first page after creating an item so pagination stays aligned', async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      id: index + 1,
      user_id: 1,
      word_phrase: `word-${index + 1}`,
      translation: `translation-${index + 1}`,
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    }));
    const refreshedFirstPage = [
      {
        id: 99,
        user_id: 1,
        word_phrase: 'new-word',
        translation: 'new-translation',
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:10:00Z',
        updated_at: '2023-10-27T10:10:00Z',
      },
      ...firstPage.slice(0, 19),
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(firstPage),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 99 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(refreshedFirstPage),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(firstPage);
      expect(result.current.hasMore).toBe(true);
    });

    await act(async () => {
      await result.current.createVocabularyItem({
        word_phrase: 'new-word',
        translation: 'new-translation',
      });
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/vocabulary/item',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8010/api/vocabulary?limit=20&offset=0',
      expect.objectContaining({
        method: 'GET',
      })
    );
    expect(result.current.recentVocabulary).toEqual(refreshedFirstPage);
  });

  it('should fetch vocabulary with search query and limit=100', async () => {
    const mockVocabularyResponse = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockVocabularyResponse),
    });

    const { result } = renderHook(() => useRecentVocabulary('hej'));

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary?search_query=hej&precise=false&limit=100&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });
  it('should include precise=true when precise search is enabled', async () => {
    const mockVocabularyResponse = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockVocabularyResponse),
    });

    const { result } = renderHook(() => useRecentVocabulary('hej', true));

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary?search_query=hej&precise=true&limit=100&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });

  it('should refetch when search query changes', async () => {
    const mockVocabularyResponse1 = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    const mockVocabularyResponse2 = [
      {
        id: 2,
        user_id: 1,
        word_phrase: 'bra',
        translation: 'good',
        example_phrase: 'Jag mår bra idag.',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:05:00Z',
        updated_at: '2023-10-27T10:05:00Z',
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockVocabularyResponse1),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockVocabularyResponse2),
      });

    const { result, rerender } = renderHook(
      ({ searchQuery, precise }) => useRecentVocabulary(searchQuery, precise),
      { initialProps: { searchQuery: '', precise: false } }
    );

    // Initial load
    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse1);
    });

    // Change search query
    rerender({ searchQuery: 'bra', precise: false });

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse2);
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8010/api/vocabulary?limit=20&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/vocabulary?search_query=bra&precise=false&limit=100&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });
  it('should refetch when precise search flag changes', async () => {
    const mockVocabularyResponse1 = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
    ];

    const mockVocabularyResponse2 = [
      {
        id: 2,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hi',
        example_phrase: 'Hej!',
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-28T10:00:00Z',
        updated_at: '2023-10-28T10:00:00Z',
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockVocabularyResponse1),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockVocabularyResponse2),
      });

    const { result, rerender } = renderHook(
      ({ precise }) => useRecentVocabulary('hej', precise),
      { initialProps: { precise: false } }
    );

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse1);
    });

    rerender({ precise: true });

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(mockVocabularyResponse2);
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8010/api/vocabulary?search_query=hej&precise=false&limit=100&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/vocabulary?search_query=hej&precise=true&limit=100&offset=0',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });

  it('should handle fetch error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: 'Failed to fetch recent vocabulary: HTTP 500' }),
    });

    const { result } = renderHook(() => useRecentVocabulary('test'));

    await waitFor(() => {
      expect(result.current.error).toBe('Failed to fetch recent vocabulary: HTTP 500');
      expect(result.current.loading).toBe(false);
      expect(result.current.recentVocabulary).toEqual([]);
    });
  });

  it('should create vocabulary item successfully', async () => {
    const mockCreatedItem = {
      id: 3,
      user_id: 1,
      word_phrase: 'tack',
      translation: 'thanks',
      example_phrase: 'Tack så mycket!',
      in_learn: true,
      last_learned: null,
      created_at: '2023-10-27T10:10:00Z',
      updated_at: '2023-10-27T10:10:00Z',
    };
    const refreshedVocabulary = [mockCreatedItem];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCreatedItem),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(refreshedVocabulary),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Create new item
    await act(async () => {
      await result.current.createVocabularyItem({
        word_phrase: 'tack',
        translation: 'thanks',
        example_phrase: 'Tack så mycket!',
      });
    });

    // Verify API was called with correct data
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary/item',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          word_phrase: 'tack',
          translation: 'thanks',
          example_phrase: 'Tack så mycket!',
        }),
      })
    );

    expect(mockFetch).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8010/api/vocabulary?limit=20&offset=0',
      expect.objectContaining({
        method: 'GET',
      })
    );

    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual(refreshedVocabulary);
    });
  });

  it('should handle create vocabulary item error', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Failed to create vocabulary item: HTTP 500' }),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Try to create item - should throw
    await act(async () => {
      await expect(
        result.current.createVocabularyItem({
          word_phrase: 'tack',
          translation: 'thanks',
        })
      ).rejects.toThrow('Failed to create vocabulary item: HTTP 500');
    });
  });

  it('should update vocabulary item successfully', async () => {
    const initialItem = {
      id: 1,
      user_id: 1,
      word_phrase: 'hej',
      translation: 'hello',
      example_phrase: 'Hej, hur mår du?',
      extra_info: null,
      in_learn: true,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    };

    const updatedItem = {
      ...initialItem,
      word_phrase: 'hej då',
      translation: 'goodbye',
      updated_at: '2023-10-27T10:05:00Z',
    };

    // Mock initial fetch response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([initialItem]),
    });

    // Mock update response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedItem),
    });
    // Mock refetch response after update
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([updatedItem]),
    });

    const { result } = renderHook(() => useRecentVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.recentVocabulary).toEqual([initialItem]);
    });

    // Update item
    await act(async () => {
      await result.current.updateVocabularyItem(1, {
        word_phrase: 'hej då',
        translation: 'goodbye',
      });
    });

    // Verify API was called with correct data
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary/1',
      expect.objectContaining({
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          word_phrase: 'hej då',
          translation: 'goodbye',
        }),
      })
    );

    // Verify state was updated from refetched list after update
    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual([updatedItem]);
    });
  });

  it('should handle update vocabulary item error', async () => {
    const initialItem = {
      id: 1,
      user_id: 1,
      word_phrase: 'hej',
      translation: 'hello',
      example_phrase: 'Hej, hur mår du?',
      extra_info: null,
      in_learn: true,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([initialItem]),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Failed to update vocabulary item: HTTP 500' }),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Try to update item - should throw
    await act(async () => {
      await expect(
        result.current.updateVocabularyItem(1, {
          word_phrase: 'hej då',
        })
      ).rejects.toThrow('Failed to update vocabulary item: HTTP 500');
    });
  });

  it('should delete vocabulary item successfully', async () => {
    const initialItems = [
      {
        id: 1,
        user_id: 1,
        word_phrase: 'hej',
        translation: 'hello',
        example_phrase: 'Hej, hur mår du?',
        extra_info: null,
        in_learn: true,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:00:00Z',
        updated_at: '2023-10-27T10:00:00Z',
      },
      {
        id: 2,
        user_id: 1,
        word_phrase: 'bra',
        translation: 'good',
        example_phrase: 'Jag mår bra idag.',
        extra_info: null,
        in_learn: true,
        last_learned: null,
        learned_times: 0,
        created_at: '2023-10-27T10:05:00Z',
        updated_at: '2023-10-27T10:05:00Z',
      },
    ];

    // Mock initial fetch response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(initialItems),
    });

    // Mock delete response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ message: 'Vocabulary item deleted successfully' }),
    });

    const { result } = renderHook(() => useRecentVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.recentVocabulary).toEqual(initialItems);
    });

    // Delete item
    await act(async () => {
      await result.current.deleteVocabularyItem(1);
    });

    // Verify API was called with correct data
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary/1',
      expect.objectContaining({
        method: 'DELETE',
      })
    );

    // Verify state was updated directly (item removed)
    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual([initialItems[1]]);
    });
  });

  it('should handle delete vocabulary item error', async () => {
    const initialItem = {
      id: 1,
      user_id: 1,
      word_phrase: 'hej',
      translation: 'hello',
      example_phrase: 'Hej, hur mår du?',
      extra_info: null,
      in_learn: true,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([initialItem]),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Failed to delete vocabulary item: HTTP 500' }),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Try to delete item - should throw
    await act(async () => {
      await expect(
        result.current.deleteVocabularyItem(1)
      ).rejects.toThrow('Failed to delete vocabulary item: HTTP 500');
    });
  });

  it('should decrement pagination offset after deleting a loaded item', async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      id: index + 1,
      user_id: 1,
      word_phrase: `word-${index + 1}`,
      translation: `translation-${index + 1}`,
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      last_learned: null,
      learned_times: 0,
      created_at: '2023-10-27T10:00:00Z',
      updated_at: '2023-10-27T10:00:00Z',
    }));

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(firstPage),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ message: 'Vocabulary item deleted successfully' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

    const { result } = renderHook(() => useRecentVocabulary());

    await waitFor(() => {
      expect(result.current.recentVocabulary).toHaveLength(20);
      expect(result.current.hasMore).toBe(true);
    });

    await act(async () => {
      await result.current.deleteVocabularyItem(1);
    });

    await act(async () => {
      await result.current.loadMore();
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8010/api/vocabulary?limit=20&offset=19',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });
});

describe('useVocabularyStats', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch vocabulary stats successfully', async () => {
    const mockStatsResponse = {
      words_in_learn_count: 4,
      words_skipped_count: 6,
      overall_words_count: 10,
      words_prioritized_count: 3,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStatsResponse),
    });

    const { result } = renderHook(() => useVocabularyStats());

    await waitFor(() => {
      expect(result.current.stats).toEqual(mockStatsResponse);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary/stats',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
  });

  it('should handle vocabulary stats fetch error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Failed to fetch vocabulary stats' }),
    });

    const { result } = renderHook(() => useVocabularyStats());

    await waitFor(() => {
      expect(result.current.error).toBe('Failed to fetch vocabulary stats');
      expect(result.current.loading).toBe(false);
      expect(result.current.stats).toBeNull();
    });
  });
});

describe('improveVocabularyItem', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  // Create a mock API object that simulates the real useApi behavior
  const mockApi = {
    post: async <T>(url: string, body?: unknown, options: Omit<ApiClientOptions, "method" | "body"> = {}): Promise<T> => {
      const response = await mockFetch(url, {
        ...options,
        method: 'POST',
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        throw new Error(`Failed to improve vocabulary item: HTTP ${response.status}`);
      }
      return response.json();
    },
    // Add other methods if needed for completeness, though not used in these tests
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    apiClient: vi.fn(),
  } as unknown as ReturnType<typeof useApi>;

  it('should improve vocabulary item with all_fields mode successfully', async () => {
    const mockResponse = {
      translation: 'hello',
      example_phrase: 'Hej, hur mår du?',
      extra_info: 'en-word, noun, base form: hej',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await improveVocabularyItem(mockApi, 'hej', VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS);

    expect(result).toEqual(mockResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/vocabulary/improve'),
      {
        method: 'POST',
        body: JSON.stringify({
          word_phrase: 'hej',
          mode: VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS,
        }),
      }
    );
  });

  it('should improve vocabulary item with example_only mode successfully', async () => {
    const mockResponse = {
      example_phrase: 'Hej, hur mår du?',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await improveVocabularyItem(mockApi, 'hej', VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY);

    expect(result).toEqual(mockResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/vocabulary/improve'),
      {
        method: 'POST',
        body: JSON.stringify({
          word_phrase: 'hej',
          mode: VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY,
        }),
      }
    );
  });

  it('should handle improve vocabulary item error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({}),
    });

    await expect(improveVocabularyItem(mockApi, 'hej', VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS)).rejects.toThrow(
      'Failed to improve vocabulary item: HTTP 500'
    );
  });

  it('should handle network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    await expect(improveVocabularyItem(mockApi, 'hej', VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS)).rejects.toThrow('Network error');
  });
});
