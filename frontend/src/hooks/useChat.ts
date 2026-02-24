import { v4 as uuidv4 } from 'uuid';
import { useState, useCallback, useEffect, useRef } from 'react';
import { useApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';

interface NewsSource {
  title: string;
  url: string;
  date: string;
}

interface ServerChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  sources?: NewsSource[] | null;
}

interface ChatHistoryResponse {
  chat_id: string;
  latest_id: number;
  messages: ServerChatMessage[];
}

interface ChatMessage {
  id: string;
  serverId?: number;
  role: 'user' | 'assistant';
  content: string;
  sources?: NewsSource[] | null;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  isFetchingHistory: boolean;
  error: string | null;
  sendMessage: (message: string, ttsExpected?: boolean, speed?: number) => Promise<void>;
  startNewChat: () => Promise<void>;
  clearError: () => void;
  refreshHistory: () => Promise<void>;
}

const CLIENT_ID = uuidv4();
const POLL_INTERVAL_MS = 5000;
const HISTORY_LIMIT = 200;

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingHistory, setIsFetchingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { get, post, delete: apiDelete } = useApi();
  const { token } = useAuth();
  const channelRef = useRef<BroadcastChannel | null>(null);
  const fetchInProgressRef = useRef<boolean>(false);
  const currentChatIdRef = useRef<string | null>(null);
  const lastMessageIdRef = useRef<number>(0);

  const mapServerMessage = useCallback((message: ServerChatMessage): ChatMessage => {
    return {
      id: `server-${message.id}`,
      serverId: message.id,
      role: message.role,
      content: message.content,
      sources: message.sources ?? undefined,
    };
  }, []);

  const mergeServerMessages = useCallback((previous: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] => {
    if (incoming.length === 0) {
      return previous;
    }

    const next = [...previous];
    const knownServerIds = new Set(
      next
        .map((message) => message.serverId)
        .filter((value): value is number => typeof value === 'number')
    );

    for (const incomingMessage of incoming) {
      const optimisticIndex = next.findIndex(
        (message) =>
          typeof message.serverId !== 'number' &&
          message.role === incomingMessage.role &&
          message.content === incomingMessage.content
      );

      if (optimisticIndex >= 0) {
        next.splice(optimisticIndex, 1);
      }

      if (typeof incomingMessage.serverId === 'number' && knownServerIds.has(incomingMessage.serverId)) {
        continue;
      }

      if (typeof incomingMessage.serverId === 'number') {
        knownServerIds.add(incomingMessage.serverId);
      }
      next.push(incomingMessage);
    }

    return next;
  }, []);

  const fetchHistory = useCallback(async (force: boolean = false) => {
    if ((!force && isLoading) || fetchInProgressRef.current || !token) return;

    fetchInProgressRef.current = true;
    setIsFetchingHistory(true);
    try {
      const endpoint = `/api/chat/history?after_id=${lastMessageIdRef.current}&limit=${HISTORY_LIMIT}`;
      const data = await get<ChatHistoryResponse>(endpoint);
      const serverMessages = (data.messages ?? []).map(mapServerMessage);
      const chatChanged = currentChatIdRef.current !== data.chat_id;

      if (chatChanged) {
        currentChatIdRef.current = data.chat_id;
        lastMessageIdRef.current = data.latest_id;
        setMessages(serverMessages);
      } else {
        setMessages(prev => mergeServerMessages(prev, serverMessages));
        if (data.latest_id !== lastMessageIdRef.current) {
          lastMessageIdRef.current = data.latest_id;
        }
      }
    } catch (err) {
      console.error('Failed to fetch chat history:', err);
      setError('Failed to load chat history. Starting fresh.');
      setMessages([]);
      currentChatIdRef.current = null;
      lastMessageIdRef.current = 0;
    } finally {
      setIsFetchingHistory(false);
      fetchInProgressRef.current = false;
    }
  }, [get, isLoading, mapServerMessage, mergeServerMessages, token]);

  // Initial fetch
  useEffect(() => {
    fetchHistory();
    // Only run on mount, but keep fetchHistory in deps for correctness
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll for cross-device synchronization while chat is mounted
  useEffect(() => {
    if (!token) return;

    const intervalId = window.setInterval(() => {
      void fetchHistory();
    }, POLL_INTERVAL_MS);

    const handleWindowFocus = () => {
      void fetchHistory();
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        void fetchHistory();
      }
    };

    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchHistory, token]);

  // Same-browser tab synchronization (Broadcast Channel)
  useEffect(() => {
    const channel = new BroadcastChannel('runestone_chat_sync');
    channelRef.current = channel;

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'CHAT_UPDATED' && event.data?.sender !== CLIENT_ID) {
        void fetchHistory();
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
    async (userMessage: string, ttsExpected: boolean = false, speed: number = 1.0) => {
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
        const data = await post<{ message: string; sources?: NewsSource[] | null }>('/api/chat/message', {
          message: userMessage.trim(),
          tts_expected: ttsExpected,
          speed: speed,
        });

        const assistantMessage: ChatMessage = {
          id: uuidv4(),
          role: 'assistant',
          content: data.message,
          sources: data.sources ?? undefined,
        };

        setMessages((prev) => [...prev, assistantMessage]);
        broadcastChange();
        await fetchHistory(true);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        setError(errorMessage);
        console.error('Chat error:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [post, isLoading, broadcastChange, fetchHistory]
  );

  const startNewChat = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await apiDelete('/api/chat/history');
      setMessages([]);
      currentChatIdRef.current = null;
      lastMessageIdRef.current = 0;
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
    isFetchingHistory,
    error,
    sendMessage,
    startNewChat,
    clearError,
    refreshHistory: fetchHistory,
  };
};
