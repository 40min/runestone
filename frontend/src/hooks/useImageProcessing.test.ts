import { renderHook, waitFor, act } from '@testing-library/react';
import useImageProcessing from './useImageProcessing';

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('useImageProcessing', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  it('should process image successfully', async () => {
    const mockResponse = {
      ocr_result: {
        text: 'Sample text',
        character_count: 11,
      },
      analysis: {
        grammar_focus: {
          topic: 'Present tense',
          explanation: 'Focus on present tense usage',
          has_explicit_rules: true,
        },
        vocabulary: [
          { swedish: 'hej', english: 'hello' },
        ],
      },
      processing_successful: true,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await result.current.processImage(file);

    await waitFor(() => {
      expect(result.current.result).toEqual(mockResponse);
      expect(result.current.error).toBeNull();
      expect(result.current.isProcessing).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/process', {
      method: 'POST',
      body: expect.any(FormData),
    });
  });

  it('should handle API error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ error: 'Processing failed' }),
    });

    const { result } = renderHook(() => useImageProcessing());

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    await act(async () => {
      await result.current.processImage(file);
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Processing failed');
      expect(result.current.result).toBeNull();
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
      expect(result.current.result).toBeNull();
      expect(result.current.isProcessing).toBe(false);
    });
  });

  it('should reset state', async () => {
    const { result } = renderHook(() => useImageProcessing());

    // First set some state by processing an image
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        ocr_result: { text: 'test', character_count: 4 },
        analysis: { grammar_focus: { topic: 'test', explanation: 'test', has_explicit_rules: false }, vocabulary: [] },
        processing_successful: true,
      }),
    });

    await act(async () => {
      await result.current.processImage(file);
    });
    await waitFor(() => {
      expect(result.current.result).not.toBeNull();
    });

    act(() => {
      result.current.reset();
    });

    await waitFor(() => {
      expect(result.current.result).toBeNull();
      expect(result.current.error).toBeNull();
      expect(result.current.isProcessing).toBe(false);
      expect(result.current.progress).toBe(0);
    });
  });

  it('should update progress during processing', async () => {
    const mockResponse = {
      ocr_result: { text: 'Sample text', character_count: 11 },
      analysis: {
        grammar_focus: { topic: 'Present tense', explanation: 'Focus on present tense usage', has_explicit_rules: true },
        vocabulary: [{ swedish: 'hej', english: 'hello' }],
      },
      processing_successful: true,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
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
    const mockResponse = {
      ocr_result: { text: 'Sample text', character_count: 11 },
      analysis: {
        grammar_focus: { topic: 'Present tense', explanation: 'Focus on present tense usage', has_explicit_rules: true },
        vocabulary: [{ swedish: 'hej', english: 'hello' }],
      },
      processing_successful: true,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
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
      expect(result.current.result).toBeNull();
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
      expect(result.current.error).toBe('response.json is not a function');
      expect(result.current.result).toBeNull();
      expect(result.current.isProcessing).toBe(false);
    });
  });
});