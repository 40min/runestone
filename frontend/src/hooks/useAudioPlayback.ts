import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

interface UseAudioPlaybackReturn {
  isPlaying: boolean;
  isConnected: boolean;
  error: string | null;
}



/**
 * Hook for playing streamed TTS audio via WebSocket.
 */
export const useAudioPlayback = (enabled: boolean): UseAudioPlaybackReturn => {
  const { token } = useAuth();
  const [isPlaying, setIsPlaying] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const chunkQueueRef = useRef<ArrayBuffer[]>([]);
  const isCompleteRef = useRef<boolean>(false);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const endedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // --- Callbacks first to avoid TDZ ---

  const cleanupWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const cleanupMediaSource = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (endedTimeoutRef.current) {
      clearTimeout(endedTimeoutRef.current);
      endedTimeoutRef.current = null;
    }

    if (audioRef.current) {
      audioRef.current.pause();
      try {
        if (audioRef.current.src) {
          audioRef.current.removeAttribute('src');
          audioRef.current.load();
        }
      } catch {
        // Silent catch
      }

      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    }

    if (mediaSourceRef.current) {
      if (mediaSourceRef.current.readyState === 'open') {
        try {
          mediaSourceRef.current.endOfStream();
        } catch {
          // Ignore
        }
      }
      mediaSourceRef.current = null;
    }

    sourceBufferRef.current = null;
    chunkQueueRef.current = [];
    isCompleteRef.current = false;
  }, []);

  const processQueue = useCallback(() => {
    const sb = sourceBufferRef.current;
    const ms = mediaSourceRef.current;

    if (!sb || sb.updating || chunkQueueRef.current.length === 0) {
      if (sb && !sb.updating && chunkQueueRef.current.length === 0 && isCompleteRef.current && ms && ms.readyState === 'open') {
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

  const initializeMediaSource = useCallback(() => {
    cleanupMediaSource();

    const mediaSource = new MediaSource();
    mediaSourceRef.current = mediaSource;

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
        const mimeType = 'audio/mpeg';
        const sb = mediaSource.addSourceBuffer(mimeType);
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
        setError('Streaming audio initialization failed');
      }
    };

    mediaSource.addEventListener('sourceopen', onSourceOpen);
  }, [cleanupMediaSource, processQueue]);

  // --- Effects last ---

  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;

    audio.onplay = () => {
      setIsPlaying(true);
    };
    audio.onended = () => {
      setIsPlaying(false);
      if (endedTimeoutRef.current) clearTimeout(endedTimeoutRef.current);
      endedTimeoutRef.current = setTimeout(() => {
        setIsPlaying(current => {
          if (!current) {
            cleanupMediaSource();
          }
          return current;
        });
      }, 100);
    };
    audio.onpause = () => {
      setIsPlaying(false);
    };
    audio.onwaiting = () => {};
    audio.onstalled = () => {};
    audio.onerror = () => {
      if (audio.error && audio.src && !audio.src.startsWith('blob:')) {
        console.error('Audio element error:', audio.error.message, 'code:', audio.error.code);
      }
      setIsPlaying(false);
    };
    return () => {
      if (endedTimeoutRef.current) {
        clearTimeout(endedTimeoutRef.current);
        endedTimeoutRef.current = null;
      }
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    };
  }, [cleanupMediaSource]);

  useEffect(() => {
    if (!enabled || !token) {
      cleanupWebSocket();
      cleanupMediaSource();
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
            const arrayBuffer = await event.data.arrayBuffer();
            chunkQueueRef.current.push(arrayBuffer);

            if (!mediaSourceRef.current) {
              initializeMediaSource();
            } else {
              processQueue();
            }
          } else {
            const data = JSON.parse(event.data);
            if (data.status === 'complete') {
              isCompleteRef.current = true;

              const sb = sourceBufferRef.current;
              const ms = mediaSourceRef.current;

              if (ms && ms.readyState === 'open' && sb && !sb.updating && chunkQueueRef.current.length === 0) {
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
          if (ws !== wsRef.current) return;
          setIsConnected(false);
          reconnectTimeoutRef.current = setTimeout(() => {
            if (enabled && token) connect();
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
      cleanupMediaSource();
    };
  }, [enabled, token, cleanupWebSocket, cleanupMediaSource, initializeMediaSource, processQueue]);

  return { isPlaying, isConnected, error };
};
