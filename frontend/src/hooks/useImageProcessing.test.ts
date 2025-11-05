import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import useImageProcessing, { type OCRResult } from './useImageProcessing';

// Mock config
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8010',
}));

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Mock AuthContext
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    token: null,
    userData: null,
    login: vi.fn(),
    logout: vi.fn(),
    isAuthenticated: () => false,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

describe('useImageProcessing', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockFetch.mockReset();
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
      await result.current.processImage(file, false); // Pass recognizeOnly as false
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
      await result.current.processImage(file, false);
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
      await result.current.processImage(file, false);
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
      await result.current.processImage(file, false);
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
      await result.current.processImage(file, false);
    });

    // Check that progress updates occurred
    expect(result.current.progress).toBe(100);
  });

  it('should set and then clear currentImage during the full processing cycle', async () => {
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

    // Step 1: Call recognizeImage which sets currentImage
    await act(async () => {
      await result.current.recognizeImage(file);
    });

    // Verify currentImage is set after OCR (URL.createObjectURL is mocked to return 'mock-url')
    expect(result.current.currentImage).not.toBeNull();
    expect(result.current.currentImage).toBe('mock-url');
    expect(result.current.ocrResult).toEqual(mockOcrResponse);

    // Step 2: Call analyzeText which clears currentImage in its finally block
    await act(async () => {
      await result.current.analyzeText(mockOcrResponse.text);
    });

    // Verify currentImage is cleared after analysis
    expect(result.current.currentImage).toBeNull();
    expect(result.current.analysisResult).toEqual(mockAnalysisResponse);
    expect(result.current.isProcessing).toBe(false);
  });

  it('should handle malformed JSON response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.reject(new Error('Invalid JSON')),
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file, false);
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
      json: () => Promise.reject(new Error('ocrResponse.json is not a function')),
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file, false);
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Unknown error');
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
      await result.current.processImage(file, false);
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
      await result.current.processImage(file, false);
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

  // New tests for recognizeImage and analyzeText in isolation
  it('recognizeImage should return OCRResult on success', async () => {
    const mockOcrResponse = { text: 'Isolated OCR text', character_count: 18 };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockOcrResponse),
    });

    const { result } = renderHook(() => useImageProcessing());
    const file = new File(['test'], 'test.png', { type: 'image/png' });

    let ocrData: OCRResult | null = null;
    await act(async () => {
      ocrData = await result.current.recognizeImage(file);
    });

    expect(ocrData).toEqual(mockOcrResponse);
    expect(result.current.ocrResult).toEqual(mockOcrResponse);
    expect(result.current.processingStep).toBe('DONE');
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith('http://localhost:8010/api/ocr', {
      method: 'POST',
      body: expect.any(FormData),
    });
  });

  it('recognizeImage should set error on API failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ error: 'Invalid image' }),
    });

    const { result } = renderHook(() => useImageProcessing());
    const file = new File(['test'], 'test.png', { type: 'image/png' });

    let ocrData: OCRResult | null = null;
    await act(async () => {
      ocrData = await result.current.recognizeImage(file);
    });

    expect(ocrData).toBeNull();
    expect(result.current.ocrResult).toBeNull();
    expect(result.current.error).toBe('Invalid image');
    expect(result.current.processingStep).toBe('IDLE');
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('analyzeText should set analysisResult on success (no resources needed)', async () => {
    const mockAnalysisResponse = {
      grammar_focus: { topic: 'Verbs', explanation: 'Verb forms', has_explicit_rules: false },
      vocabulary: [],
      core_topics: ['verbs'],
      search_needed: { should_search: false, query_suggestions: [] },
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockAnalysisResponse),
    });

    const { result } = renderHook(() => useImageProcessing());
    const textToAnalyze = 'This is a test.';

    await act(async () => {
      await result.current.analyzeText(textToAnalyze);
    });

    expect(result.current.analysisResult).toEqual(mockAnalysisResponse);
    expect(result.current.resourcesResult).toBeNull();
    expect(result.current.processingStep).toBe('DONE');
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith('http://localhost:8010/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: textToAnalyze }),
    });
  });

  it('analyzeText should set analysisResult and resourcesResult on success (resources needed)', async () => {
    const mockAnalysisResponse = {
      grammar_focus: { topic: 'Nouns', explanation: 'Noun declension', has_explicit_rules: true },
      vocabulary: [],
      core_topics: ['nouns'],
      search_needed: { should_search: true, query_suggestions: ['Swedish nouns'] },
    };
    const mockResourcesResponse = { extra_info: 'Noun resources' };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAnalysisResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResourcesResponse),
      });

    const { result } = renderHook(() => useImageProcessing());
    const textToAnalyze = 'Many nouns.';

    await act(async () => {
      await result.current.analyzeText(textToAnalyze);
    });

    expect(result.current.analysisResult).toEqual(mockAnalysisResponse);
    expect(result.current.resourcesResult).toBe(mockResourcesResponse.extra_info);
    expect(result.current.processingStep).toBe('DONE');
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenNthCalledWith(1, 'http://localhost:8010/api/analyze', expect.any(Object));
    expect(mockFetch).toHaveBeenNthCalledWith(2, 'http://localhost:8010/api/resources', expect.any(Object));
  });

  it('analyzeText should set error on API failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ error: 'Analysis failed' }),
    });

    const { result } = renderHook(() => useImageProcessing());
    const textToAnalyze = 'Some text.';

    await act(async () => {
      await result.current.analyzeText(textToAnalyze);
    });

    expect(result.current.analysisResult).toBeNull();
    expect(result.current.resourcesResult).toBeNull();
    expect(result.current.error).toBe('Analysis failed');
    expect(result.current.processingStep).toBe('IDLE');
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});
