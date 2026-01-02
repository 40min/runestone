import { v4 as uuidv4 } from 'uuid';
import { useState, useCallback, useRef, useEffect } from 'react';
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
  clearError: () => void;
}

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const api = useApi();
  const messagesRef = useRef<ChatMessage[]>([]);

  // Keep messagesRef in sync with messages state
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const sendMessage = useCallback(
    async (userMessage: string) => {
      if (!userMessage.trim() || isLoading) return;

      const newUserMessage: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content: userMessage.trim(),
      };

      // Add user message to chat
      setMessages((prev) => [...prev, newUserMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const data = await api<{ message: string }>('/api/chat/message', {
          method: 'POST',
          body: {
            message: userMessage.trim(),
            history: messagesRef.current.map(({ role, content }) => ({ role, content })),
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

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearError,
  };
};
