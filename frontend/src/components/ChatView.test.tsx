import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

describe('ChatView', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockClear();
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
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Hej! Jag mår bra, tack!' }),
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button');

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
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Hej! Jag mår bra, tack!' }),
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Hej! Hur mår du?' } });
    fireEvent.click(screen.getByRole('button'));

    // Wait for user message to appear
    await waitFor(() => {
      expect(screen.getByText('Hej! Hur mår du?')).toBeInTheDocument();
    });

    // Wait for assistant message to appear
    await waitFor(() => {
      expect(screen.getByText('Hej! Jag mår bra, tack!')).toBeInTheDocument();
    });
  });

  it('shows loading state while waiting for response', async () => {
    mockFetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => ({ message: 'Response' }),
              }),
            100
          )
        )
    );

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(screen.getByRole('button'));

    // Check for loading indicator
    await waitFor(() => {
      expect(screen.getByText('Teacher is typing...')).toBeInTheDocument();
    });
  });

  it('displays error message when API call fails', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('clears input after sending message', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Response' }),
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText(
      'Type your message...'
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(input.value).toBe('');
    });
  });

  it('disables send button when input is empty', () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const sendButton = screen.getByRole('button');
    expect(sendButton).toBeDisabled();
  });

  it('sends message on Enter key press', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Response' }),
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyPress(input, { key: 'Enter', code: 'Enter', charCode: 13 });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('includes conversation history in API request', async () => {
    // First message
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Nice to meet you!' }),
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'My name is Alice' } });
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('My name is Alice')).toBeInTheDocument();
    });

    // Second message with history
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Your name is Alice!' }),
    });

    fireEvent.change(input, { target: { value: 'What is my name?' } });
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
      const body = JSON.parse(lastCall[1].body);
      expect(body.history).toHaveLength(2); // Previous user + assistant messages
    });
  });
});
