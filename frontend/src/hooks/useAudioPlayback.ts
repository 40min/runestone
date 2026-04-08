import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

interface UseAudioPlaybackReturn {
  isPlaying: boolean;
  isPaused: boolean;
  isConnected: boolean;
  error: string | null;
  canReplay: boolean;
  playbackMessageId: string | null;
  pendingMessageId: string | null;
  play: () => Promise<void>;
  pause: () => void;
  replayLast: () => Promise<void>;
  setExpectedMessageId: (messageId: string | null) => void;
  clearPlayback: () => void;
}

/**
 * Hook for playing streamed TTS audio via WebSocket.
 *
 * The hook keeps the latest streamed teacher reply available in memory so the
 * UI can pause, resume, and replay that reply without a round-trip.
 */
export const useAudioPlayback = (enabled: boolean): UseAudioPlaybackReturn => {
  const { token } = useAuth();
  const [isPlaying, setIsPlaying] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canReplay, setCanReplay] = useState(false);
  const [playbackMessageId, setPlaybackMessageId] = useState<string | null>(null);
  const [pendingMessageId, setPendingMessageId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const chunkQueueRef = useRef<ArrayBuffer[]>([]);
  const isCompleteRef = useRef<boolean>(false);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const expectedMessageIdRef = useRef<string | null>(null);

  const resetPlayback = useCallback((preserveExpectedMessage: boolean = false) => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (audioRef.current) {
      audioRef.current.pause();
      try {
        if (audioRef.current.src) {
          audioRef.current.removeAttribute('src');
          audioRef.current.load();
        }
      } catch {
        // Silent catch during teardown.
      }
    }

    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }

    if (mediaSourceRef.current?.readyState === 'open') {
      try {
        mediaSourceRef.current.endOfStream();
      } catch {
        // Ignore teardown races for ended streams.
      }
    }

    mediaSourceRef.current = null;
    sourceBufferRef.current = null;
    chunkQueueRef.current = [];
    isCompleteRef.current = false;
    setIsPlaying(false);
    setCanReplay(false);
    setPlaybackMessageId(null);

    if (!preserveExpectedMessage) {
      expectedMessageIdRef.current = null;
      setPendingMessageId(null);
    }
  }, []);

  const clearPlayback = useCallback(() => {
    resetPlayback();
    setError(null);
  }, [resetPlayback]);

  const cleanupWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const processQueue = useCallback(() => {
    const sb = sourceBufferRef.current;
    const ms = mediaSourceRef.current;

    if (!sb || sb.updating || chunkQueueRef.current.length === 0) {
      if (sb && !sb.updating && chunkQueueRef.current.length === 0 && isCompleteRef.current && ms?.readyState === 'open') {
        try {
          ms.endOfStream();
          isCompleteRef.current = false;
        } catch (e) {
          console.warn('Error ending stream in processQueue:', e);
        }
      }
      return;
    }

    if (!ms || ms.readyState !== 'open') {
      return;
    }

    const nextChunk = chunkQueueRef.current.shift()!;
    try {
      sb.appendBuffer(nextChunk);
    } catch (e) {
      console.error('Failed to append buffer from queue:', e);
      chunkQueueRef.current.unshift(nextChunk);
    }
  }, []);

  const initializeMediaSource = useCallback((messageId: string | null) => {
    resetPlayback(true);

    const mediaSource = new MediaSource();
    mediaSourceRef.current = mediaSource;
    setPlaybackMessageId(messageId);

    const url = URL.createObjectURL(mediaSource);
    objectUrlRef.current = url;
    if (audioRef.current) {
      audioRef.current.src = url;
    }

    const onSourceOpen = () => {
      mediaSource.removeEventListener('sourceopen', onSourceOpen);

      if (mediaSource.readyState !== 'open') {
        console.warn('MediaSource not open in sourceopen handler:', mediaSource.readyState);
        return;
      }

      try {
        const sb = mediaSource.addSourceBuffer('audio/mpeg');
        sourceBufferRef.current = sb;

        sb.addEventListener('updateend', () => {
          if (chunkQueueRef.current.length > 0) {
            processQueue();
          } else if (isCompleteRef.current && !sb.updating && mediaSource.readyState === 'open') {
            try {
              mediaSource.endOfStream();
              isCompleteRef.current = false;
            } catch (e) {
              console.warn('Error calling pending endOfStream:', e);
            }
          }
        });

        sb.addEventListener('error', () => {
          console.error('SourceBuffer error');
          setCanReplay(false);
          setError('Audio playback error occurred');
        });

        processQueue();

        if (audioRef.current) {
          audioRef.current.play().catch(err => {
            if (err.name !== 'AbortError') {
              console.warn('Auto-play blocked or failed:', err);
            }
          });
        }
      } catch (e) {
        console.error('Failed to add SourceBuffer:', e);
        setCanReplay(false);
        setError('Streaming audio initialization failed');
      }
    };

    mediaSource.addEventListener('sourceopen', onSourceOpen);
  }, [processQueue, resetPlayback]);

  const playInternal = useCallback(async (restartFromBeginning: boolean) => {
    const audio = audioRef.current;
    if (!audio || !canReplay) {
      return;
    }

    const atEnd =
      audio.ended ||
      (Number.isFinite(audio.duration) && audio.duration > 0 && audio.currentTime >= audio.duration - 0.05);

    if (restartFromBeginning || atEnd) {
      try {
        audio.currentTime = 0;
      } catch {
        // Ignore browsers that reject seeking during stream transitions.
      }
    }

    try {
      await audio.play();
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError('Audio playback error occurred');
      }
    }
  }, [canReplay]);

  const play = useCallback(async () => {
    await playInternal(false);
  }, [playInternal]);

  const replayLast = useCallback(async () => {
    await playInternal(true);
  }, [playInternal]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const setExpectedMessageId = useCallback((messageId: string | null) => {
    expectedMessageIdRef.current = messageId;
    setPendingMessageId(messageId);
  }, []);

  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;

    audio.onplay = () => {
      setIsPlaying(true);
    };
    audio.onended = () => {
      setIsPlaying(false);
    };
    audio.onpause = () => {
      setIsPlaying(false);
    };
    audio.onerror = () => {
      if (audio.error && audio.src && !audio.src.startsWith('blob:')) {
        console.error('Audio element error:', audio.error.message, 'code:', audio.error.code);
      }
      setCanReplay(false);
      setIsPlaying(false);
    };

    return () => {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    };
  }, []);

  useEffect(() => {
    if (!enabled || !token) {
      cleanupWebSocket();
      clearPlayback();
      return;
    }

    const connect = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let wsUrl: string;

        if (API_BASE_URL.startsWith('http')) {
          const base = API_BASE_URL.replace(/^http/, 'ws').replace(/\/$/, '');
          wsUrl = `${base}/api/ws/audio?token=${token}`;
        } else {
          const host = window.location.host;
          const normalizedPath = API_BASE_URL.replace(/^\/+/, '').replace(/\/+$/, '');
          const path = normalizedPath ? `/${normalizedPath}` : '';
          wsUrl = `${protocol}//${host}${path}/api/ws/audio?token=${token}`;
        }

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
        };

        ws.onmessage = async (event) => {
          if (event.data instanceof Blob) {
            if (expectedMessageIdRef.current || !mediaSourceRef.current) {
              const streamMessageId = expectedMessageIdRef.current;
              expectedMessageIdRef.current = null;
              setPendingMessageId(null);
              initializeMediaSource(streamMessageId);
            }

            const arrayBuffer = await event.data.arrayBuffer();
            chunkQueueRef.current.push(arrayBuffer);
            setCanReplay(true);

            if (sourceBufferRef.current) {
              processQueue();
            }
          } else {
            const data = JSON.parse(event.data);
            if (data.status === 'complete') {
              isCompleteRef.current = true;

              const sb = sourceBufferRef.current;
              const ms = mediaSourceRef.current;

              if (ms?.readyState === 'open' && sb && !sb.updating && chunkQueueRef.current.length === 0) {
                try {
                  ms.endOfStream();
                  isCompleteRef.current = false;
                } catch (e) {
                  console.warn('Error calling endOfStream:', e);
                }
              }
            }
          }
        };

        ws.onerror = (e) => {
          console.error('Audio WebSocket error:', e);
        };

        ws.onclose = () => {
          if (ws !== wsRef.current) {
            return;
          }

          setIsConnected(false);
          reconnectTimeoutRef.current = setTimeout(() => {
            if (enabled && token) {
              connect();
            }
          }, 3000);
        };
      } catch (err) {
        setError('Failed to establish audio connection');
        console.error(err);
      }
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      cleanupWebSocket();
      clearPlayback();
    };
  }, [clearPlayback, cleanupWebSocket, enabled, initializeMediaSource, processQueue, token]);

  return {
    isPlaying,
    isPaused: canReplay && !isPlaying,
    isConnected,
    error,
    canReplay,
    playbackMessageId,
    pendingMessageId,
    play,
    pause,
    replayLast,
    setExpectedMessageId,
    clearPlayback,
  };
};
