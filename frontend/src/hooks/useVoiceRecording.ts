import { useState, useCallback, useRef } from 'react';
import { useApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';

interface UseVoiceRecordingReturn {
  isRecording: boolean;
  isProcessing: boolean;
  recordedDuration: number;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<string | null>;
  cancelRecording: () => void;
  error: string | null;
  clearError: () => void;
}

const MAX_DURATION_SECONDS = 300;

export const useVoiceRecording = (improve: boolean = true): UseVoiceRecordingReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [recordedDuration, setRecordedDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const { post } = useApi();
  const { token } = useAuth();

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const durationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(0);

  const cleanup = useCallback(() => {
    // Stop duration tracking
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }

    // Stop all tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Reset recorder
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
  }, []);

  const startRecording = useCallback(async () => {
    if (!token) {
      setError('Authentication required');
      return;
    }

    setError(null);
    audioChunksRef.current = [];
    setRecordedDuration(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Use WebM Opus for good compression and browser compatibility
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(1000); // Collect data every second
      setIsRecording(true);
      startTimeRef.current = Date.now();

      // Track duration
      durationIntervalRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
        setRecordedDuration(elapsed);

        // Auto-stop at max duration
        if (elapsed >= MAX_DURATION_SECONDS) {
          mediaRecorder.stop();
        }
      }, 1000);

    } catch (err) {
      cleanup();
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setError('Microphone permission denied. Please allow microphone access.');
        } else if (err.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone.');
        } else {
          setError(`Failed to access microphone: ${err.message}`);
        }
      } else {
        setError('Failed to start recording');
      }
    }
  }, [token, cleanup]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (!mediaRecorderRef.current || !isRecording) {
      return null;
    }

    setIsRecording(false);
    setIsProcessing(true);

    return new Promise((resolve) => {
      const mediaRecorder = mediaRecorderRef.current!;

      mediaRecorder.onstop = async () => {
        // Create blob from chunks
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });

        cleanup();

        if (audioBlob.size === 0) {
          setIsProcessing(false);
          setError('No audio recorded');
          resolve(null);
          return;
        }

        try {
          // Send to backend
          const formData = new FormData();
          formData.append('file', audioBlob, 'recording.webm');
          formData.append('improve', String(improve));

          const data = await post<{ text: string }>('/api/chat/transcribe-voice', formData);

          setIsProcessing(false);
          resolve(data.text);
        } catch (err) {
          setIsProcessing(false);
          const errorMessage = err instanceof Error ? err.message : 'Failed to transcribe voice';
          setError(errorMessage);
          resolve(null);
        }
      };

      mediaRecorder.stop();
    });
  }, [isRecording, improve, post, cleanup]);

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    cleanup();
    setIsRecording(false);
    setIsProcessing(false);
    setRecordedDuration(0);
  }, [isRecording, cleanup]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    isRecording,
    isProcessing,
    recordedDuration,
    startRecording,
    stopRecording,
    cancelRecording,
    error,
    clearError,
  };
};
