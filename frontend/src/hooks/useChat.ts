import { v4 as uuidv4 } from 'uuid';
import { useState, useCallback, useEffect, useRef } from 'react';
import { useApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';

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

const CLIENT_ID = uuidv4();

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { get, post, delete: apiDelete } = useApi();
  const { token } = useAuth();
  const lastFetchRef = useRef<number>(0);
  const channelRef = useRef<BroadcastChannel | null>(null);

  const fetchInProgressRef = useRef<boolean>(false);

  const fetchHistory = useCallback(async () => {
    // Prevent redundant calls if already loading, fetching or no token
    if (isLoading || fetchInProgressRef.current || !token) return;

    fetchInProgressRef.current = true;
    setIsLoading(true);
    try {
      const data = await get<{ messages: ChatMessage[] }>('/api/chat/history');
      const newMessages = data.messages || [];

      setMessages(prev => {
        // Simple comparison to avoid unnecessary state updates
        if (prev.length === newMessages.length &&
            prev.every((msg, i) => msg.id === newMessages[i].id && msg.content === newMessages[i].content)) {
          return prev;
        }
        return newMessages;
      });
      lastFetchRef.current = Date.now();
    } catch (err) {
      console.error('Failed to fetch chat history:', err);
      setError('Failed to load chat history. Starting fresh.');
      setMessages([]);
    } finally {
      setIsLoading(false);
      fetchInProgressRef.current = false;
    }
  }, [get, isLoading, token]);

  // Initial fetch
  useEffect(() => {
    fetchHistory();
    // Only run on mount, but keep fetchHistory in deps for correctness
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tab synchronization (Broadcast Channel)
  useEffect(() => {
    const channel = new BroadcastChannel('runestone_chat_sync');
    channelRef.current = channel;

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'CHAT_UPDATED' && event.data?.sender !== CLIENT_ID) {
        // Known change from another tab, fetch immediately
        fetchHistory();
      }
    };

    channel.addEventListener('message', handleMessage);

    return () => {
      channel.removeEventListener('message', handleMessage);
      channel.close();
      channelRef.current = null;
    };
  }, [fetchHistory]);

  const broadcastChange = useCallback(() => {
    if (channelRef.current) {
      channelRef.current.postMessage({ type: 'CHAT_UPDATED', sender: CLIENT_ID });
    }
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
        const data = await post<{ message: string }>('/api/chat/message', {
          message: userMessage.trim(),
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
    [post, isLoading, broadcastChange]
  );

  const startNewChat = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await apiDelete('/api/chat/history');
      setMessages([]);
      broadcastChange();
    } catch (err) {
      console.error('Failed to clear chat history:', err);
      setError('Failed to start a new chat. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [apiDelete, broadcastChange]);

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
