import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatView from './ChatView';
import { AuthProvider } from '../context/AuthContext';

// Mock the API
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn((key) => {
    if (key === 'runestone_token') return 'test-token';
    if (key === 'runestone_user_data') {
      return JSON.stringify({
        id: '1',
        email: 'test@example.com',
        username: 'testuser',
      });
    }
    return null;
  }),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// Setup mock fetch to handle all requests
const setupMockFetch = () => {
  mockFetch.mockImplementation((url, options) => {
    if (url.includes('/api/chat/history') && options?.method === 'DELETE') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    }
    if (url.includes('/api/chat/history')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ messages: [] }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ message: 'Response' }),
    });
  });
};

// Helper to get the send button (last button in the chat input area)
const getSendButton = () => {
  const buttons = screen.getAllByRole('button');
  return buttons[buttons.length - 1];
};

describe('ChatView', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockClear();
    setupMockFetch();
  });

  it('renders the chat interface', () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    expect(screen.getByText('Chat with Your Swedish Teacher')).toBeInTheDocument();
    expect(
      screen.getByText(/Ask questions about Swedish vocabulary, grammar/i)
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
  });

  it('shows empty state when no messages', () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    expect(screen.getByText('Start a conversation')).toBeInTheDocument();
    expect(
      screen.getByText(/Ask me anything about Swedish!/i)
    ).toBeInTheDocument();
  });

  it('sends a message when send button is clicked', async () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = getSendButton();

    fireEvent.change(input, { target: { value: 'Hej! Hur mår du?' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/chat/message'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer test-token',
          }),
          body: expect.stringContaining('Hej! Hur mår du?'),
        })
      );
    });
  });

  it('displays user and assistant messages', async () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Hej! Hur mår du?' } });
    fireEvent.click(getSendButton());

    // Wait for user message to appear
    await waitFor(() => {
      expect(screen.getByText('Hej! Hur mår du?')).toBeInTheDocument();
    });

    // Wait for assistant message to appear
    await waitFor(() => {
      expect(screen.getByText('Response')).toBeInTheDocument();
    });
  });

  it('disables send button when input is empty', () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const sendButton = getSendButton();
    expect(sendButton).toBeDisabled();
  });

  it('sends message on Enter key press', async () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('shows loading state while waiting for response', async () => {
    let resolvePromise: (value: Response | PromiseLike<Response>) => void;
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      return new Promise((resolve) => {
        resolvePromise = resolve;
      });
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(getSendButton());

    // Check for loading indicator
    await waitFor(() => {
      expect(screen.getByText('Teacher is typing...')).toBeInTheDocument();
    });

    // Resolve the promise to clean up
    await act(async () => {
      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });
  });

  it('displays error message when API call fails', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      return Promise.reject(new Error('Network error'));
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(getSendButton());

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('clears input after sending message', async () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(
      'Type your message...'
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(getSendButton());

    await waitFor(() => {
      expect(input.value).toBe('');
    });
  });
});
