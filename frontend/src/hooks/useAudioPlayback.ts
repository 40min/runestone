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
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const chunkQueueRef = useRef<ArrayBuffer[]>([]);

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

  const cleanupMediaSource = useCallback(() => {
    if (mediaSourceRef.current) {
      if (mediaSourceRef.current.readyState === 'open') {
        mediaSourceRef.current.endOfStream();
      }
      mediaSourceRef.current = null;
    }
    sourceBufferRef.current = null;
    chunkQueueRef.current = [];
  }, []);

  const initializeMediaSource = useCallback(() => {
    cleanupMediaSource();

    const mediaSource = new MediaSource();
    mediaSourceRef.current = mediaSource;

    if (audioRef.current) {
      audioRef.current.src = URL.createObjectURL(mediaSource);
    }

    mediaSource.addEventListener('sourceopen', () => {
      try {
        // MP3 is usually supported as 'audio/mpeg' in MSE
        const sb = mediaSource.addSourceBuffer('audio/mpeg');
        sourceBufferRef.current = sb;

        sb.addEventListener('updateend', () => {
          if (chunkQueueRef.current.length > 0 && !sb.updating) {
            const nextChunk = chunkQueueRef.current.shift()!;
            sb.appendBuffer(nextChunk);
          }
        });

        // If we already have queued chunks, start appending
        if (chunkQueueRef.current.length > 0) {
          const nextChunk = chunkQueueRef.current.shift()!;
          sb.appendBuffer(nextChunk);
        }

        // Try to play as soon as we have data
        if (audioRef.current) {
          audioRef.current.play().catch(err => {
            console.warn('Auto-play blocked or failed:', err);
          });
        }
      } catch (e) {
        console.error('Failed to add SourceBuffer:', e);
        setError('Streaming audio not supported in this browser');
      }
    });
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
              // We don't close MSE immediately in case there's still data to play
            }
          }
        };

        ws.onerror = (e) => {
          console.error('Audio WebSocket error:', e);
          setError('Audio connection error');
        };

        ws.onclose = () => {
          setIsConnected(false);
          console.log('Audio WebSocket closed');
        };
      } catch (err) {
        setError('Failed to establish audio connection');
        console.error(err);
      }
    };

    connect();

    return () => {
      cleanupWebSocket();
      cleanupMediaSource();
    };
  }, [enabled, token, cleanupWebSocket, cleanupMediaSource, initializeMediaSource]);

  return { isPlaying, isConnected, error };
};
