import { renderHook, waitFor, act } from '@testing-library/react';
import useVocabulary from './useVocabulary';

// Mock config
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

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

    expect(mockFetch).toHaveBeenCalledWith('http://localhost:8010/api/vocabulary');
  });

  it('should handle fetch error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
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