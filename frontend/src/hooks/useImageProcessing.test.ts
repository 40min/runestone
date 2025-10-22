import { renderHook, waitFor, act } from '@testing-library/react';
import useImageProcessing from './useImageProcessing';

// Mock config
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('useImageProcessing', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  it('should process image successfully through all steps', async () => {
    const mockOcrResponse = {
      text: 'Sample text',
      character_count: 11,
    };

    const mockAnalysisResponse = {
      grammar_focus: {
        topic: 'Present tense',
        explanation: 'Focus on present tense usage',
        has_explicit_rules: true,
      },
      vocabulary: [
        { swedish: 'hej', english: 'hello' },
      ],
      core_topics: ['present tense', 'greetings'],
      search_needed: {
        should_search: true,
        query_suggestions: ['Swedish present tense', 'Basic Swedish grammar']
      },
    };

    const mockResourcesResponse = {
      extra_info: 'Additional learning resources here',
    };

    // Mock the three API calls
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockOcrResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAnalysisResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResourcesResponse),
      });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.ocrResult).toEqual(mockOcrResponse);
      expect(result.current.analysisResult).toEqual(mockAnalysisResponse);
      expect(result.current.resourcesResult).toBe(mockResourcesResponse.extra_info);
      expect(result.current.processingStep).toBe('DONE');
      expect(result.current.error).toBeNull();
      expect(result.current.isProcessing).toBe(false);
    });

    // Verify the three API calls were made
    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(mockFetch).toHaveBeenNthCalledWith(1, 'http://localhost:8010/api/ocr', {
      method: 'POST',
      body: expect.any(FormData),
    });
    expect(mockFetch).toHaveBeenNthCalledWith(2, 'http://localhost:8010/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: 'Sample text' }),
    });
    expect(mockFetch).toHaveBeenNthCalledWith(3, 'http://localhost:8010/api/resources', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        analysis: {
          core_topics: mockAnalysisResponse.core_topics,
          search_needed: mockAnalysisResponse.search_needed
        }
      }),
    });
  });

  it('should handle OCR API error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ error: 'OCR failed' }),
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.error).toBe('OCR failed');
      expect(result.current.ocrResult).toBeNull();
      expect(result.current.analysisResult).toBeNull();
      expect(result.current.resourcesResult).toBeNull();
      expect(result.current.processingStep).toBe('IDLE');
      expect(result.current.isProcessing).toBe(false);
    });
  });

  it('should handle network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Network error');
      expect(result.current.ocrResult).toBeNull();
      expect(result.current.analysisResult).toBeNull();
      expect(result.current.resourcesResult).toBeNull();
      expect(result.current.processingStep).toBe('IDLE');
      expect(result.current.isProcessing).toBe(false);
    });
  });

  it('should reset state', async () => {
    const { result } = renderHook(() => useImageProcessing());

    // First set some state by processing an image
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ text: 'test', character_count: 4 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          grammar_focus: { topic: 'test', explanation: 'test', has_explicit_rules: false },
          vocabulary: [],
          core_topics: ['test topic'],
          search_needed: { should_search: true, query_suggestions: ['test query'] }
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ extra_info: 'test' }),
      });

    await act(async () => {
      await result.current.processImage(file);
    });
    await waitFor(() => {
      expect(result.current.ocrResult).not.toBeNull();
    });

    act(() => {
      result.current.reset();
    });

    await waitFor(() => {
      expect(result.current.ocrResult).toBeNull();
      expect(result.current.analysisResult).toBeNull();
      expect(result.current.resourcesResult).toBeNull();
      expect(result.current.processingStep).toBe('IDLE');
      expect(result.current.error).toBeNull();
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.progress).toBe(0);
    });
  });

  it('should update progress during processing', async () => {
    const mockOcrResponse = { text: 'Sample text', character_count: 11 };
    const mockAnalysisResponse = {
      grammar_focus: { topic: 'Present tense', explanation: 'Focus on present tense usage', has_explicit_rules: true },
      vocabulary: [{ swedish: 'hej', english: 'hello' }],
      core_topics: ['present tense', 'greetings'],
      search_needed: { should_search: true, query_suggestions: ['Swedish present tense'] },
    };
    const mockResourcesResponse = { extra_info: 'Additional resources' };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockOcrResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAnalysisResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResourcesResponse),
      });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });

    await act(async () => {
      await result.current.processImage(file);
    });

    // Check that progress updates occurred
    expect(result.current.progress).toBe(100);
  });

  it('should set currentImage during processing', async () => {
    const mockOcrResponse = { text: 'Sample text', character_count: 11 };
    const mockAnalysisResponse = {
      grammar_focus: { topic: 'Present tense', explanation: 'Focus on present tense usage', has_explicit_rules: true },
      vocabulary: [{ swedish: 'hej', english: 'hello' }],
      core_topics: ['present tense', 'greetings'],
      search_needed: { should_search: true, query_suggestions: ['Swedish present tense'] },
    };
    const mockResourcesResponse = { extra_info: 'Additional resources' };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockOcrResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAnalysisResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResourcesResponse),
      });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });

    await act(async () => {
      await result.current.processImage(file);
    });

    // currentImage should be null after processing completes (cleaned up)
    await waitFor(() => {
      expect(result.current.currentImage).toBeNull();
    });
  });

  it('should handle malformed JSON response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.reject(new Error('Invalid JSON')),
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Invalid JSON');
      expect(result.current.ocrResult).toBeNull();
      expect(result.current.analysisResult).toBeNull();
      expect(result.current.resourcesResult).toBeNull();
      expect(result.current.processingStep).toBe('IDLE');
      expect(result.current.isProcessing).toBe(false);
    });
  });

  it('should handle response without json method', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.error).toBe('ocrResponse.json is not a function');
      expect(result.current.ocrResult).toBeNull();
      expect(result.current.analysisResult).toBeNull();
      expect(result.current.resourcesResult).toBeNull();
      expect(result.current.processingStep).toBe('IDLE');
      expect(result.current.isProcessing).toBe(false);
    });
  });

  it('should update processingStep during multi-step processing', async () => {
    const mockOcrResponse = { text: 'Sample text', character_count: 11 };
    const mockAnalysisResponse = {
      grammar_focus: { topic: 'Present tense', explanation: 'Focus on present tense usage', has_explicit_rules: true },
      vocabulary: [{ swedish: 'hej', english: 'hello' }],
      core_topics: ['present tense', 'greetings'],
      search_needed: { should_search: true, query_suggestions: ['Swedish present tense'] },
    };
    const mockResourcesResponse = { extra_info: 'Additional resources' };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockOcrResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAnalysisResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResourcesResponse),
      });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });

    await act(async () => {
      await result.current.processImage(file);
    });

    // Check that processingStep was updated to DONE
    await waitFor(() => {
      expect(result.current.processingStep).toBe('DONE');
    });
  });

  it('should skip resources step when should_search is false', async () => {
    const mockOcrResponse = { text: 'Sample text', character_count: 11 };
    const mockAnalysisResponse = {
      grammar_focus: { topic: 'Present tense', explanation: 'Focus on present tense usage', has_explicit_rules: true },
      vocabulary: [{ swedish: 'hej', english: 'hello' }],
      core_topics: ['present tense', 'greetings'],
      search_needed: { should_search: false, query_suggestions: [] },
    };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockOcrResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAnalysisResponse),
      });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.ocrResult).toEqual(mockOcrResponse);
      expect(result.current.analysisResult).toEqual(mockAnalysisResponse);
      expect(result.current.resourcesResult).toBeNull();
      expect(result.current.processingStep).toBe('DONE');
      expect(result.current.error).toBeNull();
      expect(result.current.isProcessing).toBe(false);
    });

    // Verify only OCR and analysis API calls were made (no resources call)
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenNthCalledWith(1, 'http://localhost:8010/api/ocr', {
      method: 'POST',
      body: expect.any(FormData),
    });
    expect(mockFetch).toHaveBeenNthCalledWith(2, 'http://localhost:8010/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: 'Sample text' }),
    });
  });
});
