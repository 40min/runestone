import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

interface UseAudioPlaybackReturn {
  isPlaying: boolean;
  isConnected: boolean;
  error: string | null;
}

interface ExtendedSourceBuffer extends SourceBuffer {
  _pendingEndOfStream?: boolean;
}

/**
 * Hook for playing streamed TTS audio via WebSocket.
 *
 * It manages the WebSocket connection to the backend and
 * plays received audio chunks using the MediaSource API for
 * low-latency streaming playback.
 */
export const useAudioPlayback = (enabled: boolean): UseAudioPlaybackReturn => {
  const { token } = useAuth();
  const [isPlaying, setIsPlaying] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<ExtendedSourceBuffer | null>(null);
  const chunkQueueRef = useRef<ArrayBuffer[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize Audio element once
  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;

    audio.onplay = () => setIsPlaying(true);
    audio.onended = () => setIsPlaying(false);
    audio.onpause = () => setIsPlaying(false);

    return () => {
      audio.pause();
      audio.src = '';
    };
  }, []);

  const cleanupWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const objectUrlRef = useRef<string | null>(null);

  const cleanupMediaSource = useCallback(() => {
    if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
    }

    if (mediaSourceRef.current) {
      if (mediaSourceRef.current.readyState === 'open') {
        try {
          mediaSourceRef.current.endOfStream();
        } catch {
          // Ignore if already closed or failing
        }
      }
      mediaSourceRef.current = null;
    }

    if (audioRef.current) {
      audioRef.current.pause();
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      audioRef.current.src = '';
    }

    sourceBufferRef.current = null;
    chunkQueueRef.current = [];
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
        // The backend provides an MP3 stream, so we use the 'audio/mpeg' MIME type.
        const mimeType = 'audio/mpeg';

        console.debug('Initializing SourceBuffer with:', mimeType);
        const sb = mediaSource.addSourceBuffer(mimeType);
        sourceBufferRef.current = sb;

        sb.addEventListener('updateend', () => {
          if (chunkQueueRef.current.length > 0 && !sb.updating && mediaSource.readyState === 'open') {
            const nextChunk = chunkQueueRef.current.shift()!;
            try {
                sb.appendBuffer(nextChunk);
            } catch (e) {
                console.error('Failed to append buffer from queue:', e);
            }
          } else if (chunkQueueRef.current.length === 0 && sb._pendingEndOfStream && !sb.updating && mediaSource.readyState === 'open') {
            try {
                mediaSource.endOfStream();
                sb._pendingEndOfStream = false;
                // Clear refs after stream is closed so next message starts fresh
                mediaSourceRef.current = null;
                sourceBufferRef.current = null;
            } catch (e) {
                console.warn('Error calling pending endOfStream:', e);
            }
          }
        });

        sb.addEventListener('error', (e) => {
            console.error('SourceBuffer error:', e);
            setError('Audio playback error occurred');
        });

        // If we already have queued chunks, start appending
        if (chunkQueueRef.current.length > 0 && !sb.updating) {
          const nextChunk = chunkQueueRef.current.shift()!;
          sb.appendBuffer(nextChunk);
        }

        // Try to play as soon as we have data
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
          wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/api/ws/audio?token=' + token;
        } else {
          // Relative URL
          const host = window.location.host;
          const path = API_BASE_URL.startsWith('/') ? API_BASE_URL : '/' + API_BASE_URL;
          wsUrl = `${protocol}//${host}${path}/api/ws/audio?token=${token}`;
        }

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
          console.log('Audio WebSocket connected');
        };

        ws.onmessage = async (event) => {
          if (event.data instanceof Blob) {
            const arrayBuffer = await event.data.arrayBuffer();

            // If MediaSource isn't ready, initialize it
            if (!mediaSourceRef.current) {
              initializeMediaSource();
            }

            if (sourceBufferRef.current && !sourceBufferRef.current.updating) {
              try {
                sourceBufferRef.current.appendBuffer(arrayBuffer);
              } catch (e) {
                console.warn('Error appending buffer directly, queuing:', e);
                chunkQueueRef.current.push(arrayBuffer);
              }
            } else {
              chunkQueueRef.current.push(arrayBuffer);
            }
          } else {
            const data = JSON.parse(event.data);
            if (data.status === 'complete') {
              console.log('Audio stream complete');
              const sb = sourceBufferRef.current;
              const ms = mediaSourceRef.current;

              if (ms && ms.readyState === 'open') {
                if (sb && sb.updating) {
                  // Wait for the final update to finish before calling endOfStream
                  sb._pendingEndOfStream = true;
                } else {
                  try {
                    ms.endOfStream();
                    mediaSourceRef.current = null;
                    sourceBufferRef.current = null;
                  } catch (e) {
                    console.warn('Error calling endOfStream:', e);
                  }
                }
              }
              // We don't null out immediately here anymore because we might need to wait for updateend
            }
          }
        };

        ws.onerror = (e) => {
          console.error('Audio WebSocket error:', e);
          // Don't set error state immediately to avoid flashing UI, let reconnection handle it
        };

        ws.onclose = () => {
          // Only reconnect if this is the active connection
          if (ws !== wsRef.current) {
            return;
          }

          console.log('Audio WebSocket closed, attempting reconnect...');
          setIsConnected(false);
          // Attempt reconnect after 3 seconds
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
      cleanupMediaSource();
    };
  }, [enabled, token, cleanupWebSocket, cleanupMediaSource, initializeMediaSource]);

  return { isPlaying, isConnected, error };
};
