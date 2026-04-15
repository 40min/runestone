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
  created_at?: string | null;
}

interface ChatHistoryResponse {
  chat_id: string;
  chat_mismatch: boolean;
  latest_id: number;
  has_more: boolean;
  history_truncated: boolean;
  messages: ServerChatMessage[];
}

interface ChatMessage {
  id: string;
  serverId?: number;
  role: 'user' | 'assistant';
  content: string;
  sources?: NewsSource[] | null;
  responseTimeMs?: number;
  createdAt?: string;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  isFetchingHistory: boolean;
  isSyncingHistory: boolean;
  historySyncNotice: string | null;
  error: string | null;
  sendMessage: (message: string, ttsExpected?: boolean, speed?: number) => Promise<string | null>;
  startNewChat: () => Promise<void>;
  clearError: () => void;
  refreshHistory: () => Promise<void>;
}

const CLIENT_ID = uuidv4();
const INITIAL_POLL_INTERVAL_MS = 5000;
const MAX_POLL_INTERVAL_MS = 60000;
const HISTORY_LIMIT = 200;
const INITIAL_HISTORY_ERROR = 'Failed to load chat history. Starting fresh.';

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingHistory, setIsFetchingHistory] = useState(false);
  const [isSyncingHistory, setIsSyncingHistory] = useState(false);
  const [historySyncNotice, setHistorySyncNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { get, post, delete: apiDelete } = useApi();
  const { token } = useAuth();
  const channelRef = useRef<BroadcastChannel | null>(null);
  const pollTimeoutRef = useRef<number | null>(null);
  const pollIntervalRef = useRef<number>(INITIAL_POLL_INTERVAL_MS);
  const fetchInProgressRef = useRef<boolean>(false);
  const currentChatIdRef = useRef<string | null>(null);
  const lastMessageIdRef = useRef<number>(0);
  const hasLoadedHistoryRef = useRef<boolean>(false);

  const clearPollTimeout = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      window.clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  const resetPollingInterval = useCallback(() => {
    pollIntervalRef.current = INITIAL_POLL_INTERVAL_MS;
  }, []);

  const extendPollingInterval = useCallback(() => {
    pollIntervalRef.current = Math.min(pollIntervalRef.current * 2, MAX_POLL_INTERVAL_MS);
  }, []);

  const mapServerMessage = useCallback((message: ServerChatMessage): ChatMessage => {
    return {
      id: `server-${message.id}`,
      serverId: message.id,
      role: message.role,
      content: message.content,
      sources: message.sources ?? undefined,
      createdAt: message.created_at ?? undefined,
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
      if (typeof incomingMessage.serverId === 'number' && knownServerIds.has(incomingMessage.serverId)) {
        continue;
      }

      const optimisticIndex = next.findIndex(
        (message) =>
          typeof message.serverId !== 'number' &&
          message.role === incomingMessage.role &&
          message.content === incomingMessage.content
      );

      if (optimisticIndex >= 0) {
        next[optimisticIndex] = {
          ...incomingMessage,
          // Keep the optimistic client id stable so UI bindings (e.g. playback controls)
          // don't break when the history poll swaps in the server-backed record.
          id: next[optimisticIndex].id,
          responseTimeMs: next[optimisticIndex].responseTimeMs,
        };
      } else {
        next.push(incomingMessage);
      }

      if (typeof incomingMessage.serverId === 'number') {
        knownServerIds.add(incomingMessage.serverId);
      }
    }

    return next;
  }, []);

  const getMaxServerId = useCallback((incoming: ChatMessage[]): number | null => {
    let maxServerId: number | null = null;
    for (const message of incoming) {
      if (typeof message.serverId === 'number') {
        maxServerId = maxServerId === null ? message.serverId : Math.max(maxServerId, message.serverId);
      }
    }
    return maxServerId;
  }, []);

  const fetchHistory = useCallback(async (force: boolean = false): Promise<boolean> => {
    if ((!force && isLoading) || fetchInProgressRef.current || !token) return false;

    fetchInProgressRef.current = true;
    setIsFetchingHistory(true);
    try {
      setError((previous) => (previous === INITIAL_HISTORY_ERROR ? null : previous));
      let page = 0;
      let keepFetching = true;
      let syncingOlderPages = false;
      let receivedUpdates = false;

      while (keepFetching && page < 20) {
        const clientChatQuery = currentChatIdRef.current
          ? `&client_chat_id=${encodeURIComponent(currentChatIdRef.current)}`
          : '';
        const endpoint = `/api/chat/history?after_id=${lastMessageIdRef.current}&limit=${HISTORY_LIMIT}${clientChatQuery}`;
        const data = await get<ChatHistoryResponse>(endpoint);
        hasLoadedHistoryRef.current = true;
        const serverMessages = (data.messages ?? []).map(mapServerMessage);
        const maxIncomingId = getMaxServerId(serverMessages);
        const chatChanged = data.chat_mismatch || currentChatIdRef.current !== data.chat_id;
        receivedUpdates = receivedUpdates || chatChanged || serverMessages.length > 0;

        if (chatChanged) {
          currentChatIdRef.current = data.chat_id;
          lastMessageIdRef.current = maxIncomingId ?? 0;
          setMessages(serverMessages);
          setHistorySyncNotice(data.history_truncated ? 'Some older messages are no longer available.' : null);
        } else {
          setMessages(prev => mergeServerMessages(prev, serverMessages));
          if (typeof maxIncomingId === 'number' && maxIncomingId > lastMessageIdRef.current) {
            lastMessageIdRef.current = maxIncomingId;
          }
          if (data.history_truncated) {
            setHistorySyncNotice('Some older messages are no longer available.');
          }
        }

        const canAdvanceCursor = typeof maxIncomingId === 'number' && maxIncomingId > 0;
        keepFetching = data.has_more && canAdvanceCursor;

        if (data.has_more && !canAdvanceCursor) {
          keepFetching = false;
          setHistorySyncNotice('More messages exist on server. Please refresh again.');
        }

        if (keepFetching) {
          syncingOlderPages = true;
          setIsSyncingHistory(true);
        }

        page += 1;
      }

      if (!syncingOlderPages) {
        setIsSyncingHistory(false);
      }

      return receivedUpdates;
    } catch (err) {
      console.error('Failed to fetch chat history:', err);
      if (!hasLoadedHistoryRef.current) {
        setError(INITIAL_HISTORY_ERROR);
        setMessages([]);
        setHistorySyncNotice(null);
        currentChatIdRef.current = null;
        lastMessageIdRef.current = 0;
      }

      setIsSyncingHistory(false);
      return false;
    } finally {
      setIsSyncingHistory(false);
      setIsFetchingHistory(false);
      fetchInProgressRef.current = false;
    }
  }, [get, getMaxServerId, isLoading, mapServerMessage, mergeServerMessages, token]);

  // Initial fetch
  useEffect(() => {
    void fetchHistory();
    // Only run on mount, but keep fetchHistory in deps for correctness
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll for cross-device synchronization while chat is mounted
  useEffect(() => {
    if (!token) return;

    let isCancelled = false;

    const scheduleNextPoll = () => {
      if (isCancelled) {
        return;
      }

      clearPollTimeout();
      pollTimeoutRef.current = window.setTimeout(async () => {
        if (document.hidden) {
          scheduleNextPoll();
          return;
        }

        const hasUpdates = await fetchHistory();
        if (isCancelled) {
          return;
        }

        if (hasUpdates) {
          resetPollingInterval();
        } else {
          extendPollingInterval();
        }

        scheduleNextPoll();
      }, pollIntervalRef.current);
    };

    const handleWindowFocus = () => {
      resetPollingInterval();
      void fetchHistory().finally(scheduleNextPoll);
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        resetPollingInterval();
        void fetchHistory().finally(scheduleNextPoll);
      }
    };

    resetPollingInterval();
    scheduleNextPoll();

    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isCancelled = true;
      clearPollTimeout();
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [clearPollTimeout, extendPollingInterval, fetchHistory, resetPollingInterval, token]);

  // Same-browser tab synchronization (Broadcast Channel)
  useEffect(() => {
    const channel = new BroadcastChannel('runestone_chat_sync');
    channelRef.current = channel;

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'CHAT_UPDATED' && event.data?.sender !== CLIENT_ID) {
        resetPollingInterval();
        void fetchHistory();
      }
    };

    channel.addEventListener('message', handleMessage);

    return () => {
      channel.removeEventListener('message', handleMessage);
      channel.close();
      channelRef.current = null;
    };
  }, [fetchHistory, resetPollingInterval]);

  const broadcastChange = useCallback(() => {
    if (channelRef.current) {
      channelRef.current.postMessage({ type: 'CHAT_UPDATED', sender: CLIENT_ID });
    }
  }, []);

  const sendMessage = useCallback(
    async (userMessage: string, ttsExpected: boolean = false, speed: number = 1.0) => {
      if (!userMessage.trim() || isLoading) return null;
      const startedAt = performance.now();

      const newUserMessage: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content: userMessage.trim(),
        createdAt: new Date().toISOString(),
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
          responseTimeMs: Math.max(0, Math.round(performance.now() - startedAt)),
          createdAt: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
        resetPollingInterval();
        broadcastChange();
        void fetchHistory(true);
        return assistantMessage.id;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        setError(errorMessage);
        console.error('Chat error:', err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [post, isLoading, broadcastChange, fetchHistory, resetPollingInterval]
  );

  const startNewChat = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await apiDelete('/api/chat/history');
      setMessages([]);
      setHistorySyncNotice(null);
      currentChatIdRef.current = null;
      lastMessageIdRef.current = 0;
      resetPollingInterval();
      broadcastChange();
    } catch (err) {
      console.error('Failed to clear chat history:', err);
      setError('Failed to start a new chat. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [apiDelete, broadcastChange, resetPollingInterval]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const refreshHistory = useCallback(async () => {
    resetPollingInterval();
    await fetchHistory(true);
  }, [fetchHistory, resetPollingInterval]);

  return {
    messages,
    isLoading,
    isFetchingHistory,
    isSyncingHistory,
    historySyncNotice,
    error,
    sendMessage,
    startNewChat,
    clearError,
    refreshHistory,
  };
};
