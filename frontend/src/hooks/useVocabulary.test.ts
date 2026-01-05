import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import useVocabulary, { useRecentVocabulary, improveVocabularyItem } from './useVocabulary';
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
    mockFetch.mockClear();
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
    mockFetch.mockClear();
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
      expect(result.current.error).toBeNull();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/vocabulary?limit=20',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
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
      'http://localhost:8010/api/vocabulary?search_query=hej&limit=100&precise=false',
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
      'http://localhost:8010/api/vocabulary?search_query=hej&limit=100&precise=true',
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
      'http://localhost:8010/api/vocabulary?limit=20',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/vocabulary?search_query=bra&limit=100&precise=false',
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
      'http://localhost:8010/api/vocabulary?search_query=hej&limit=100&precise=false',
      expect.objectContaining({
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/vocabulary?search_query=hej&limit=100&precise=true',
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

    // Mock initial fetch response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    });

    // Mock create response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockCreatedItem),
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

    // Verify state was updated directly with the new item
    await waitFor(() => {
      expect(result.current.recentVocabulary).toEqual([mockCreatedItem]);
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

    // Verify state was updated directly with the updated item
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
});

describe('improveVocabularyItem', () => {
  beforeEach(() => {
    mockFetch.mockClear();
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
