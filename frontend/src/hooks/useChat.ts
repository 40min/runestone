import { v4 as uuidv4 } from 'uuid';
import { useState, useCallback, useEffect, useRef } from 'react';
import { useApi } from '../utils/api';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (message: string) => Promise<void>;
  startNewChat: () => Promise<void>;
  clearError: () => void;
}

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const api = useApi();
  const lastFetchRef = useRef<number>(0);
  const STALE_THRESHOLD = 10000; // 10 seconds

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api<{ messages: ChatMessage[] }>('/api/chat/history');
      setMessages(data.messages);
      lastFetchRef.current = Date.now();
    } catch (err) {
      console.error('Failed to fetch chat history:', err);
      setError('Failed to load chat history. Starting fresh.');
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  // Initial fetch
  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Tab synchronization (Broadcast Channel + Window Focus/Visibility)
  useEffect(() => {
    const channel = new BroadcastChannel('runestone_chat_sync');

    const handleMessage = (event: MessageEvent) => {
      if (event.data === 'CHAT_UPDATED') {
        // Known change, fetch immediately
        fetchHistory();
      }
    };

    const handleFocus = () => {
      // Only re-fetch if we haven't fetched recently
      const isStale = Date.now() - lastFetchRef.current > STALE_THRESHOLD;
      if (isStale) {
        fetchHistory();
      }
    };

    channel.addEventListener('message', handleMessage);
    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        handleFocus();
      }
    });

    return () => {
      channel.removeEventListener('message', handleMessage);
      channel.close();
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleFocus);
    };
  }, [fetchHistory]);

  const broadcastChange = useCallback(() => {
    const channel = new BroadcastChannel('runestone_chat_sync');
    channel.postMessage('CHAT_UPDATED');
    channel.close();
  }, []);

  const sendMessage = useCallback(
    async (userMessage: string) => {
      if (!userMessage.trim() || isLoading) return;

      const newUserMessage: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content: userMessage.trim(),
      };

      // Add user message to chat immediately for UI responsiveness
      setMessages((prev) => [...prev, newUserMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const data = await api<{ message: string }>('/api/chat/message', {
          method: 'POST',
          body: {
            message: userMessage.trim(),
          },
        });

        const assistantMessage: ChatMessage = {
          id: uuidv4(),
          role: 'assistant',
          content: data.message,
        };

        setMessages((prev) => [...prev, assistantMessage]);
        broadcastChange();
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        setError(errorMessage);
        console.error('Chat error:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [api, isLoading, broadcastChange]
  );

  const startNewChat = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api('/api/chat/history', { method: 'DELETE' });
      setMessages([]);
      broadcastChange();
    } catch (err) {
      console.error('Failed to clear chat history:', err);
      setError('Failed to start a new chat. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [api, broadcastChange]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    startNewChat,
    clearError,
  };
};
