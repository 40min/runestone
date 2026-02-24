// @vitest-environment jsdom
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

const buildHistoryPayload = (
  messages: unknown[] = [],
  chatId: string = 'chat-1',
  latestId: number = 0,
  hasMore: boolean = false,
  historyTruncated: boolean = false
) => ({
  chat_id: chatId,
  latest_id: latestId,
  chat_mismatch: false,
  has_more: hasMore,
  history_truncated: historyTruncated,
  messages,
});

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

// Setup default mocks for all tests - always return empty history for GET requests
const setupDefaultMocks = () => {
  mockFetch.mockImplementation((_url, options) => {
    if (options?.method === 'GET' || !options?.method) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ message: 'Response' }),
    });
  });
};

describe('useChat', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    setupDefaultMocks();
  });

  it('should initialize with empty messages', async () => {
    const { result } = renderHook(() => useChat());

    // Wait for any async operations
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.messages).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('should send a message successfully', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Hej! Jag mår bra, tack!' }),
      });
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

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
          tts_expected: false,
          speed: 1,
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
    let callCount = 0;
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      callCount++;
      if (callCount === 2) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: 'Your name is Alice!' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Nice to meet you, Alice!' }),
      });
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

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
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Internal server error' }),
      });
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.sendMessage('Test message');
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Internal server error');
      expect(result.current.isLoading).toBe(false);
      // User message should still be added
      expect(result.current.messages).toHaveLength(1);
    });
  });

  it('should handle network error', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      return Promise.reject(new Error('Network error'));
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

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
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.sendMessage('  Test message  ');
    });

    await waitFor(() => {
      expect(result.current.messages[0].content).toBe('Test message');
    });
  });

  it('should not send empty messages', async () => {
    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.sendMessage('');
    });

    // Only the history fetch should have been called
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(result.current.messages).toHaveLength(0);
  });

  it('should not send whitespace-only messages', async () => {
    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.sendMessage('   ');
    });

    // Only the history fetch should have been called
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(result.current.messages).toHaveLength(0);
  });

  it('should clear error', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Error message' }),
      });
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

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
    const messagePromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      return messagePromise;
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

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
      await messagePromise;
    });

    // Should no longer be loading
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('should clear error when sending new message', async () => {
    let callCount = 0;
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-1', 0)),
        });
      }
      callCount++;
      if (callCount === 2) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: 'Success' }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Error' }),
      });
    });

    const { result } = renderHook(() => useChat());

    // Wait for initial history fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

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

  it('should poll history with after_id and append delta messages', async () => {
    let historyCallCount = 0;
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'GET' || !options?.method) {
        historyCallCount++;
        if (historyCallCount === 1) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve(buildHistoryPayload([{ id: 2, role: 'assistant', content: 'Initial message' }], 'chat-1', 2)),
          });
        }

        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              buildHistoryPayload([{ id: 3, role: 'assistant', content: 'New from other device' }], 'chat-1', 3)
            ),
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'ok' }),
      });
    });

    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    await act(async () => {
      await result.current.refreshHistory();
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].content).toBe('New from other device');
    });

    const historyUrls = mockFetch.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/chat/history'));
    expect(historyUrls.some((url) => url.includes('after_id=2'))).toBe(true);
  });

  it('should clear local messages when chat_id changes', async () => {
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'GET' || !options?.method) {
        if (String(url).includes('after_id=0')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve(
                buildHistoryPayload([{ id: 1, role: 'assistant', content: 'Old chat message' }], 'chat-1', 1)
              ),
          });
        }

        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(buildHistoryPayload([], 'chat-2', 0)),
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'ok' }),
      });
    });

    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    await act(async () => {
      await result.current.refreshHistory();
    });

    await waitFor(() => {
      expect(result.current.messages).toEqual([]);
    });
  });

  it('should advance after_id to last received message id, not latest_id', async () => {
    let historyCallCount = 0;
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'GET' || !options?.method) {
        historyCallCount++;
        if (historyCallCount === 1) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve(
                buildHistoryPayload(
                  [
                    { id: 1, role: 'assistant', content: 'M1' },
                    { id: 2, role: 'assistant', content: 'M2' },
                  ],
                  'chat-1',
                  5
                )
              ),
          });
        }

        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              buildHistoryPayload([{ id: 3, role: 'assistant', content: 'M3' }], 'chat-1', 5)
            ),
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'ok' }),
      });
    });

    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    await act(async () => {
      await result.current.refreshHistory();
    });

    const historyUrls = mockFetch.mock.calls
      .map((call) => String(call[0]))
      .filter((historyUrl) => historyUrl.includes('/api/chat/history'));
    expect(historyUrls.some((historyUrl) => historyUrl.includes('after_id=2'))).toBe(true);
    expect(historyUrls.some((historyUrl) => historyUrl.includes('after_id=5'))).toBe(false);
  });

  it('should auto-drain additional pages when has_more is true', async () => {
    let historyCallCount = 0;
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'GET' || !options?.method) {
        historyCallCount++;
        if (historyCallCount === 1) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve(
                buildHistoryPayload([{ id: 1, role: 'assistant', content: 'Page1' }], 'chat-1', 3, true)
              ),
          });
        }
        if (historyCallCount === 2) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve(
                buildHistoryPayload([{ id: 2, role: 'assistant', content: 'Page2' }], 'chat-1', 3, true)
              ),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              buildHistoryPayload([{ id: 3, role: 'assistant', content: 'Page3' }], 'chat-1', 3, false)
            ),
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'ok' }),
      });
    });

    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.messages).toHaveLength(3));
    expect(result.current.isSyncingHistory).toBe(false);
    expect(result.current.messages.map((message) => message.content)).toEqual(['Page1', 'Page2', 'Page3']);
  });
});
