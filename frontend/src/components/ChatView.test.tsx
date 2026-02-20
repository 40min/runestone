import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatView from './ChatView';
import { AuthProvider } from '../context/AuthContext';

// Mock the API
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock URL.createObjectURL and crypto.randomUUID
global.URL.createObjectURL = vi.fn(() => 'blob:test-image-url');
global.crypto.randomUUID = vi.fn(() => 'test-uuid');

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
      json: () =>
        Promise.resolve({
          message: 'Response',
          sources: [
            {
              title: 'Nyhetstitel',
              url: 'https://example.com/news',
              date: '2026-02-05',
            },
          ],
        }),
    });
  });
};

// Helper to get the send button
const getSendButton = () => {
  return screen.getByRole('button', { name: /send message/i });
};

describe('ChatView', () => {
  const resetLocalStorage = () => {
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'runestone_token') return 'test-token';
      if (key === 'runestone_user_data') {
        return JSON.stringify({
          id: '1',
          email: 'test@example.com',
          username: 'testuser',
        });
      }
      return null;
    });
  };

  beforeEach(() => {
    mockFetch.mockClear();
    vi.clearAllMocks();
    resetLocalStorage();
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

    // Sources should render as link with date
    expect(screen.getByRole('link', { name: 'Nyhetstitel' })).toHaveAttribute(
      'href',
      'https://example.com/news'
    );
    expect(screen.getByRole('link', { name: 'Nyhetstitel' })).toHaveAttribute('target', '_blank');
    expect(screen.getByRole('link', { name: 'Nyhetstitel' })).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText('2026-02-05')).toBeInTheDocument();
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
      expect(screen.getByText('Teacher is thinking...')).toBeInTheDocument();
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

  it('clears uploaded images when starting a new chat', async () => {
    // Setup mock to return existing chat history so the "New Chat" button is enabled
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              messages: [{ id: '1', role: 'user', content: 'hello' }],
            }),
        });
      }
      if (url.includes('/api/chat/image')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: 'Translation for image' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    const { container } = render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    // 1. Upload an image
    const file = new File(['(⌐□_□)'], 'chucknorris.png', { type: 'image/png' });
    const fileInput = container.querySelector('input[type="file"]');
    expect(fileInput).toBeInTheDocument();

    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }

    // 2. Verifies the image is shown
    await waitFor(() => {
      expect(screen.getByAltText('Uploaded')).toBeInTheDocument();
    });

    // 3. Ensure button is enabled (since we mocked history to have messages)
    await waitFor(() => {
      const button = screen.getByRole('button', { name: /Start New Chat/i });
      expect(button).not.toBeDisabled();
    });

    // 4. Click "Start New Chat"
    const newChatButton = screen.getByRole('button', { name: /Start New Chat/i });
    fireEvent.click(newChatButton);

    // 5. Verifies the image is removed
    await waitFor(() => {
      expect(screen.queryByAltText('Uploaded')).not.toBeInTheDocument();
    });
  });

  it('shows processing indicator when uploading an image', async () => {
    let resolvePromise: (value: Response | PromiseLike<Response>) => void;
    let uploadPromise: Promise<Response>; // Declare uploadPromise here
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      if (url.includes('/api/chat/image')) {
        uploadPromise = new Promise((resolve) => {
          resolvePromise = resolve;
        });
        return uploadPromise;
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });

    const { container } = render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const file = new File(['(⌐□_□)'], 'test.png', { type: 'image/png' });
    const fileInput = container.querySelector('input[type="file"]');

    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }

    // Check for processing indicator
    await waitFor(() => {
      expect(screen.getByText('Analyzing image...')).toBeInTheDocument();
    });

    // Resolve the promise to clean up
    await act(async () => {
      resolvePromise!({
        ok: true,
        json: async () => ({ message: 'Translation' }),
      } as Response);
    });
    await uploadPromise; // Wait for the mock fetch promise to fully resolve

    // After resolution, the loading indicator should be gone
    await waitFor(() => {
      expect(screen.queryByText('Analyzing image...')).not.toBeInTheDocument();
    });
  });

  it('displays upload error message', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      if (url.includes('/api/chat/image')) {
        return Promise.reject(new Error('Upload failed'));
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });

    const { container } = render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    const fileInput = container.querySelector('input[type="file"]');

    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }

    // Wait for error message to appear
    await waitFor(() => {
      expect(screen.getByText('Upload failed')).toBeInTheDocument();
    });
  });

  it('displays images in sidebar after upload', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      if (url.includes('/api/chat/image')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: 'Translation' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });

    const { container } = render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    const fileInput = container.querySelector('input[type="file"]');

    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }

    // Wait for image to appear in sidebar
    await waitFor(() => {
      expect(screen.getByAltText('Uploaded')).toBeInTheDocument();
    });
  });

  it('disables inputs during image upload', async () => {
    let resolvePromise: (value: Response | PromiseLike<Response>) => void;
    let uploadPromise: Promise<Response>; // Declare uploadPromise here
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      if (url.includes('/api/chat/image')) {
        uploadPromise = new Promise((resolve) => {
          resolvePromise = resolve;
        });
        return uploadPromise;
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });

    const { container } = render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...') as HTMLInputElement;
    const sendButton = getSendButton();
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    // Type a message to enable send button
    fireEvent.change(input, { target: { value: 'Test message' } });
    expect(sendButton).not.toBeDisabled();

    // Start upload
    const file = new File(['test'], 'test.png', { type: 'image/png' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Wait for upload to start
    await waitFor(() => {
      expect(screen.getByText('Analyzing image...')).toBeInTheDocument();
    });

    // All inputs should be disabled during upload
    expect(input).toBeDisabled();
    expect(sendButton).toBeDisabled();
    expect(fileInput).toBeDisabled();

    // Resolve the upload
    await act(async () => {
      resolvePromise!({
        ok: true,
        json: async () => ({ message: 'Translation' }),
      } as Response);
    });

    await uploadPromise; // Inputs should be enabled again
    await waitFor(() => {
      expect(input).not.toBeDisabled();
      expect(fileInput).not.toBeDisabled();
    });
  });

  it('scrolls to bottom when loading state starts', async () => {
    let resolvePromise: (value: Response | PromiseLike<Response>) => void;
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ messages: [] }),
        });
      }
      // Return a pending promise for the message endpoint
      if (url.includes('/api/chat/message')) {
        return new Promise((resolve) => {
          resolvePromise = resolve;
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
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

    // Wait for loading indicator to appear
    await waitFor(() => {
      expect(screen.getByText('Teacher is thinking...')).toBeInTheDocument();
    });

    // Verify scrollIntoView was called when loading started
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();

    // Resolve the promise to clean up
    await act(async () => {
      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });
  });

  it('scrolls to the beginning of the last message on initial history load', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.includes('/api/chat/history')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              messages: [
                { id: 'm1', role: 'user', content: 'Hej' },
                { id: 'm2', role: 'assistant', content: 'Hej! Hur mår du?' },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ message: 'Response' }),
      });
    });

    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Hej! Hur mår du?')).toBeInTheDocument();
    });

    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: 'start' })
    );
  });

  it('scrolls to the beginning of a newly arrived assistant message', async () => {
    render(
      <AuthProvider>
        <ChatView />
      </AuthProvider>
    );

    // Wait for initial history fetch
    await waitFor(() => {
      expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
    });

    (window.HTMLElement.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mockClear();

    const input = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(getSendButton());

    await waitFor(() => {
      expect(screen.getByText('Response')).toBeInTheDocument();
    });

    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: 'start' })
    );
  });
});
