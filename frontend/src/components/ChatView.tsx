import React, { useState, useRef, useEffect } from 'react';
import { Box, FormControlLabel, Checkbox, Select, MenuItem, Typography } from '@mui/material';
import { Send } from 'lucide-react';
import {
  CustomButton,
  ErrorAlert,
  ChatMessageBubble,
  ChatEmptyState,
  ChatLoadingIndicator,
  ChatInput,
  ChatContainer,
  ImageUploadButton,
  Snackbar,
  VoiceRecordButton,
  VoiceToggle,
} from './ui';
import { ImageSidebar } from './chat/ImageSidebar';
import { ChatHeader } from './chat/ChatHeader';
import AgentMemoryModal from './chat/AgentMemoryModal';
import { useChat } from '../hooks/useChat';
import { useChatImageUpload } from '../hooks/useChatImageUpload';
import { useVoiceRecording } from '../hooks/useVoiceRecording';
import { useAudioPlayback } from '../hooks/useAudioPlayback';

const IMPROVE_TRANSCRIPTION_KEY = 'runestone_improve_transcription';
const VOICE_ENABLED_KEY = 'runestone_voice_enabled';
const SPEECH_SPEED_KEY = 'runestone_speech_speed';
const AUTOSEND_KEY = 'runestone_autosend';

const ChatView: React.FC = () => {
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastMessageRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);
  const prevIsAnyProcessingRef = useRef(false);
  const { messages, isLoading, isFetchingHistory, error, sendMessage, startNewChat, refreshHistory } = useChat();
  const { uploadedImages, uploadImage, isUploading, error: uploadError, clearImages } = useChatImageUpload();
  const [snackbarError, setSnackbarError] = useState<string | null>(null);
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);

  // Voice recording with improve option
  const [improveTranscription, setImproveTranscription] = useState(() => {
    const stored = localStorage.getItem(IMPROVE_TRANSCRIPTION_KEY);
    return stored === null ? true : stored === 'true';
  });

  const [voiceEnabled, setVoiceEnabled] = useState(() => {
    const stored = localStorage.getItem(VOICE_ENABLED_KEY);
    return stored === 'true';
  });

  const [speechSpeed, setSpeechSpeed] = useState(() => {
    const stored = localStorage.getItem(SPEECH_SPEED_KEY);
    return stored && Number.isFinite(Number(stored)) ? Number(stored) : 1.1;
  });

  const [autoSend, setAutoSend] = useState(() => {
    const stored = localStorage.getItem(AUTOSEND_KEY);
    return stored === null ? false : stored === 'true';
  });

  const {
    isRecording,
    isProcessing: isTranscribing,
    recordedDuration,
    startRecording,
    stopRecording,
    error: voiceError,
    clearError: clearVoiceError,
  } = useVoiceRecording(improveTranscription);

  const { isPlaying: isAudioPlaying } = useAudioPlayback(voiceEnabled);

  const canUseMicrophone =
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === 'function' &&
    typeof MediaRecorder !== 'undefined';

  const isAnyProcessing = isLoading || isUploading || isTranscribing || isFetchingHistory;

  const scrollToLastMessage = (behavior: ScrollBehavior, block: ScrollLogicalPosition) => {
    lastMessageRef.current?.scrollIntoView({ behavior, block, inline: 'nearest' });
  };

  // Persist settings
  useEffect(() => {
    localStorage.setItem(IMPROVE_TRANSCRIPTION_KEY, String(improveTranscription));
  }, [improveTranscription]);

  useEffect(() => {
    localStorage.setItem(VOICE_ENABLED_KEY, String(voiceEnabled));
  }, [voiceEnabled]);

  useEffect(() => {
    localStorage.setItem(SPEECH_SPEED_KEY, String(speechSpeed));
  }, [speechSpeed]);

  useEffect(() => {
    localStorage.setItem(AUTOSEND_KEY, String(autoSend));
  }, [autoSend]);

  // Show voice errors in snackbar
  useEffect(() => {
    if (voiceError) {
      setSnackbarError(voiceError);
      clearVoiceError();
    }
  }, [voiceError, clearVoiceError]);

  // Auto-scroll to bottom when messages change or loading state changes
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const isInitialLoad = messages.length > 0 && prevMessagesLengthRef.current === 0;
    const isNewMessage = messages.length > prevMessagesLengthRef.current;
    const isProcessingStarted = isAnyProcessing && !prevIsAnyProcessingRef.current;
    const isProcessingEnded = !isAnyProcessing && prevIsAnyProcessingRef.current;

    // For user messages, only scroll if near bottom to avoid disrupting reading
    // For assistant messages, always scroll to show the response
    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 150;

    if (isInitialLoad) {
      // Initial load of messages (e.g. switching back to Chat tab / history refresh)
      scrollToLastMessage('auto', 'start');
    } else if (isNewMessage) {
      const isUserMessage = messages[messages.length - 1].role === 'user';
      if (isUserMessage) {
        // For user messages, only scroll if user is already near bottom
        if (isAtBottom) {
          scrollToLastMessage('smooth', 'end');
        }
      } else {
        // For assistant messages, always scroll to the beginning of the response
        scrollToLastMessage('smooth', 'start');
      }
    } else if (isProcessingStarted) {
      // When processing starts, scroll to show loading indicator
      if (isAtBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end', inline: 'nearest' });
      }
    } else if (isProcessingEnded && messages.length > 0) {
      // When processing ends and there's an assistant message, scroll to ensure it's visible
      const lastMessageIsAssistant = messages[messages.length - 1].role === 'assistant';
      if (lastMessageIsAssistant) {
        scrollToLastMessage('smooth', 'start');
      }
    }

    prevMessagesLengthRef.current = messages.length;
    prevIsAnyProcessingRef.current = isAnyProcessing;
  }, [messages, isAnyProcessing]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const messageToSend = inputMessage.trim();
    setInputMessage('');
    await sendMessage(messageToSend, voiceEnabled, speechSpeed);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleImageUpload = async (file: File) => {
    const translationMessage = await uploadImage(file);
    if (translationMessage) {
      // Refresh chat history to show the new translation message
      await refreshHistory();
    }
  };

  const handleImageError = (message: string) => {
    setSnackbarError(message);
  };

  const handleNewChat = async () => {
    clearImages();
    await startNewChat();
  };

  const handleStartRecording = async () => {
    await startRecording();
  };

  const handleStopRecording = async () => {
    const transcribedText = await stopRecording();
    if (transcribedText) {
      if (autoSend) {
          await sendMessage(transcribedText, voiceEnabled, speechSpeed);
      } else {
        setInputMessage(transcribedText);
      }
    }
  };


  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        height: { xs: 'calc(100dvh - 58px)', md: 'calc(100vh - 74px)' },
        width: '100%',
        maxWidth: { xs: '100%', md: '100%' },
        margin: '0 auto',
        backgroundColor: '#1a102b',
        gap: 2,
      }}
    >
      {/* Main chat area */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
        }}
      >
      {/* Header */}
      <ChatHeader
        title="Chat with Your Swedish Teacher"
        subtitle="Ask questions about Swedish vocabulary, grammar, or practice conversation"
        onNewChat={handleNewChat}
        onOpenMemory={() => setIsMemoryModalOpen(true)}
        isLoading={isAnyProcessing}
        hasMessages={messages.length > 0}
      />

      {/* Messages Container */}
      <ChatContainer ref={scrollContainerRef}>
        {messages.length === 0 ? (
          <ChatEmptyState />
        ) : (
          messages.map((msg, index) => (
            <div key={msg.id} ref={index === messages.length - 1 ? lastMessageRef : undefined}>
              <ChatMessageBubble
                role={msg.role}
                content={msg.content}
                sources={msg.sources}
              />
            </div>
          ))
        )}

        {isLoading && <ChatLoadingIndicator message="Teacher is thinking..." />}
        {isUploading && <ChatLoadingIndicator message="Analyzing image..." />}
        {isTranscribing && <ChatLoadingIndicator message="Transcribing voice..." />}

        {error && <ErrorAlert message={error} />}

        <div ref={messagesEndRef} />
      </ChatContainer>

        {/* Input Area */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            pb: { xs: 'calc(8px + env(safe-area-inset-bottom))', md: 0 },
          }}
        >
          <Box
            sx={{
              display: 'flex',
              gap: { xs: 1, md: 2 },
              alignItems: 'center',
            }}
          >
            <ChatInput
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              disabled={isAnyProcessing || isRecording}
            />
            <CustomButton
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || isAnyProcessing || isRecording}
              aria-label="Send message"
              sx={{
                minWidth: { xs: '48px', md: '56px' },
                height: { xs: '48px', md: '56px' },
                borderRadius: '12px',
              }}
            >
              <Send size={20} />
            </CustomButton>
          </Box>

            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 2,
                alignItems: 'center',
                pl: 0.5,
              }}
            >
              <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                <ImageUploadButton
                  onFileSelect={handleImageUpload}
                  onError={handleImageError}
                  disabled={isAnyProcessing || isRecording}
                />
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <VoiceRecordButton
                    isRecording={isRecording}
                    isProcessing={isTranscribing}
                    duration={recordedDuration}
                    onStartRecording={handleStartRecording}
                    onStopRecording={handleStopRecording}
                    disabled={isAnyProcessing || !canUseMicrophone}
                  />
                  {!canUseMicrophone && (
                    <Typography variant="caption" sx={{ color: '#9ca3af', fontSize: '0.65rem', lineHeight: 1 }}>
                      HTTPS required
                    </Typography>
                  )}
                </Box>
              </Box>

              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={autoSend}
                      onChange={(e) => setAutoSend(e.target.checked)}
                      size="small"
                      sx={{
                        color: '#9ca3af',
                        p: 0.5,
                        '&.Mui-checked': { color: 'var(--primary-color)' },
                      }}
                    />
                  }
                  label="Autosend"
                  sx={{
                    color: '#9ca3af',
                    m: 0,
                    '& .MuiFormControlLabel-label': { fontSize: '0.75rem' },
                  }}
                />

                <FormControlLabel
                  control={
                    <Checkbox
                      checked={improveTranscription}
                      onChange={(e) => setImproveTranscription(e.target.checked)}
                      size="small"
                      sx={{
                        color: '#9ca3af',
                        p: 0.5,
                        '&.Mui-checked': {
                          color: 'var(--primary-color)',
                        },
                      }}
                    />
                  }
                  label="Improve transcription"
                  sx={{
                    color: '#9ca3af',
                    m: 0,
                    '& .MuiFormControlLabel-label': {
                      fontSize: '0.75rem',
                    },
                  }}
                />
              </Box>
            </Box>

            <Box
              sx={{
                display: 'flex',
                gap: 3,
                alignItems: 'center',
                pl: 0.5,
                mt: 0.5,
                pt: 1,
                borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              }}
            >
              <VoiceToggle
                enabled={voiceEnabled}
                onChange={setVoiceEnabled}
                isPlaying={isAudioPlaying}
                disabled={isAnyProcessing}
              />

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" sx={{ color: '#9ca3af' }}>Speed:</Typography>
                <Select
                  value={speechSpeed}
                  onChange={(e) => setSpeechSpeed(Number(e.target.value))}
                  size="small"
                  variant="standard"
                  sx={{
                    color: '#9ca3af',
                    fontSize: '0.8rem',
                    '& .MuiSelect-select': { py: 0, pr: 3 },
                    '&:before': { borderColor: '#4b5563' },
                    '&:hover:not(.Mui-disabled):before': { borderColor: '#9ca3af' }
                  }}
                >
                  {[0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25].map(speed => (
                    <MenuItem key={speed} value={speed}>{speed.toFixed(2)}x</MenuItem>
                  ))}
                </Select>
              </Box>
            </Box>
        </Box>

        {/* Upload error display */}
        {uploadError && <ErrorAlert message={uploadError} sx={{ mt: 2, mb: 0 }} />}
      </Box>

      {/* Image Sidebar */}
      <ImageSidebar images={uploadedImages} />

      {/* Validation Error Snackbar */}
      <Snackbar
        open={!!snackbarError}
        message={snackbarError || ''}
        severity="error"
        onClose={() => setSnackbarError(null)}
      />

      <AgentMemoryModal
        open={isMemoryModalOpen}
        onClose={() => setIsMemoryModalOpen(false)}
      />
    </Box>
  );
};

export default ChatView;
