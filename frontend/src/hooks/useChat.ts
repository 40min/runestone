import { v4 as uuidv4 } from 'uuid';
import { useState, useCallback, useEffect } from 'react';
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

  // Fetch history on mount
  useEffect(() => {
    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const data = await api<{ messages: ChatMessage[] }>('/api/chat/history');
        setMessages(data.messages);
      } catch (err) {
        console.error('Failed to fetch chat history:', err);
        setError('Failed to load chat history. Starting fresh.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, [api]);

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
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        setError(errorMessage);
        console.error('Chat error:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [api, isLoading]
  );

  const startNewChat = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api('/api/chat/history', { method: 'DELETE' });
      setMessages([]);
    } catch (err) {
      console.error('Failed to clear chat history:', err);
      setError('Failed to start a new chat. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [api]);

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
