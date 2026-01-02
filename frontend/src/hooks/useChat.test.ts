import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useChat } from './useChat';

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
      token: 'test-token',
      userData: null,
      login: vi.fn(),
      logout: mockLogout,
      isAuthenticated: () => true,
    }),
    AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  };
});

describe('useChat', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  it('should initialize with empty messages', () => {
    const { result } = renderHook(() => useChat());

    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should send a message successfully', async () => {
    const mockResponse = {
      message: 'Hej! Jag mår bra, tack!',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('Hej! Hur mår du?');
    });

    // Verify API was called with correct data
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/chat/message',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer test-token',
        },
        body: JSON.stringify({
          message: 'Hej! Hur mår du?',
          history: [],
        }),
      })
    );

    // Verify messages state was updated
    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0]).toEqual(
        expect.objectContaining({
          role: 'user',
          content: 'Hej! Hur mår du?',
        })
      );
      expect(result.current.messages[1]).toEqual(
        expect.objectContaining({
          role: 'assistant',
          content: 'Hej! Jag mår bra, tack!',
        })
      );
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  it('should send message with conversation history', async () => {
    const mockResponse1 = {
      message: 'Nice to meet you, Alice!',
    };

    const mockResponse2 = {
      message: 'Your name is Alice!',
    };

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse1),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse2),
      });

    const { result } = renderHook(() => useChat());

    // First message
    await act(async () => {
      await result.current.sendMessage('My name is Alice');
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    // Second message with history
    await act(async () => {
      await result.current.sendMessage('What is my name?');
    });

    // Verify second API call included history
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8010/api/chat/message',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          message: 'What is my name?',
          history: [
            { role: 'user', content: 'My name is Alice' },
            { role: 'assistant', content: 'Nice to meet you, Alice!' },
          ],
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4);
      expect(result.current.messages[2]).toEqual(
        expect.objectContaining({
          role: 'user',
          content: 'What is my name?',
        })
      );
      expect(result.current.messages[3]).toEqual(
        expect.objectContaining({
          role: 'assistant',
          content: 'Your name is Alice!',
        })
      );
    });
  });

  it('should handle API error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Internal server error' }),
    });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('Test message');
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Internal server error');
      expect(result.current.isLoading).toBe(false);
      // User message should still be added
      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(
        expect.objectContaining({
          role: 'user',
          content: 'Test message',
        })
      );
    });
  });

  it('should handle network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('Test message');
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Network error');
      expect(result.current.isLoading).toBe(false);
      expect(result.current.messages).toHaveLength(1);
    });
  });

  it('should trim whitespace from messages', async () => {
    const mockResponse = {
      message: 'Response',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('  Test message  ');
    });

    // Verify trimmed message was sent
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/chat/message',
      expect.objectContaining({
        body: JSON.stringify({
          message: 'Test message',
          history: [],
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.messages[0].content).toBe('Test message');
    });
  });

  it('should not send empty messages', async () => {
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('');
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it('should not send whitespace-only messages', async () => {
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('   ');
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it('should not send message while loading', async () => {
    mockFetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: () => Promise.resolve({ message: 'Response' }),
              }),
            100
          )
        )
    );

    const { result } = renderHook(() => useChat());

    // Start first message
    act(() => {
      result.current.sendMessage('First message');
    });

    // Try to send second message while first is loading
    await act(async () => {
      await result.current.sendMessage('Second message');
    });

    // Should only have called API once
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  it('should clear error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Error message' }),
    });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('Test');
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Error message');
    });

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it('should set loading state correctly', async () => {
    let resolvePromise: (value: unknown) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockFetch.mockReturnValueOnce(promise);

    const { result } = renderHook(() => useChat());

    expect(result.current.isLoading).toBe(false);

    act(() => {
      result.current.sendMessage('Test message');
    });

    // Should be loading immediately
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the promise
    await act(async () => {
      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
      await promise;
    });

    // Should no longer be loading
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('should maintain message order', async () => {
    const responses = [
      { message: 'Response 1' },
      { message: 'Response 2' },
      { message: 'Response 3' },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(responses[0]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(responses[1]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(responses[2]),
      });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('Message 1');
    });

    await act(async () => {
      await result.current.sendMessage('Message 2');
    });

    await act(async () => {
      await result.current.sendMessage('Message 3');
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(6);
      expect(result.current.messages[0].content).toBe('Message 1');
      expect(result.current.messages[1].content).toBe('Response 1');
      expect(result.current.messages[2].content).toBe('Message 2');
      expect(result.current.messages[3].content).toBe('Response 2');
      expect(result.current.messages[4].content).toBe('Message 3');
      expect(result.current.messages[5].content).toBe('Response 3');
    });
  });

  it('should clear error when sending new message', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ message: 'Success' }),
      });

    const { result } = renderHook(() => useChat());

    // First message fails
    await act(async () => {
      await result.current.sendMessage('First message');
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Error');
    });

    // Second message succeeds
    await act(async () => {
      await result.current.sendMessage('Second message');
    });

    await waitFor(() => {
      expect(result.current.error).toBeNull();
    });
  });
});
