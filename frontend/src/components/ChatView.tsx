import React, { useState, useRef, useEffect } from 'react';
import { Box, FormControlLabel, Checkbox } from '@mui/material';
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
import { useChat } from '../hooks/useChat';
import { useChatImageUpload } from '../hooks/useChatImageUpload';
import { useVoiceRecording } from '../hooks/useVoiceRecording';
import { useAudioPlayback } from '../hooks/useAudioPlayback';

const IMPROVE_TRANSCRIPTION_KEY = 'runestone_improve_transcription';
const VOICE_ENABLED_KEY = 'runestone_voice_enabled';

const ChatView: React.FC = () => {
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);
  const prevIsAnyProcessingRef = useRef(false);
  const { messages, isLoading, isFetchingHistory, error, sendMessage, startNewChat, refreshHistory } = useChat();
  const { uploadedImages, uploadImage, isUploading, error: uploadError, clearImages } = useChatImageUpload();
  const [snackbarError, setSnackbarError] = useState<string | null>(null);

  // Voice recording with improve option
  const [improveTranscription, setImproveTranscription] = useState(() => {
    const stored = localStorage.getItem(IMPROVE_TRANSCRIPTION_KEY);
    return stored === null ? true : stored === 'true';
  });

  const [voiceEnabled, setVoiceEnabled] = useState(() => {
    const stored = localStorage.getItem(VOICE_ENABLED_KEY);
    return stored === 'true';
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

  const isAnyProcessing = isLoading || isUploading || isTranscribing || isFetchingHistory;

  // Persist settings
  useEffect(() => {
    localStorage.setItem(IMPROVE_TRANSCRIPTION_KEY, String(improveTranscription));
  }, [improveTranscription]);

  useEffect(() => {
    localStorage.setItem(VOICE_ENABLED_KEY, String(voiceEnabled));
  }, [voiceEnabled]);

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

    const isNewMessage = messages.length > prevMessagesLengthRef.current;
    const isProcessingStarted = isAnyProcessing && !prevIsAnyProcessingRef.current;
    const isProcessingEnded = !isAnyProcessing && prevIsAnyProcessingRef.current;

    // For user messages, only scroll if near bottom to avoid disrupting reading
    // For assistant messages, always scroll to show the response
    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 150;

    if (isNewMessage) {
      const isUserMessage = messages[messages.length - 1].role === 'user';
      if (isUserMessage) {
        // For user messages, only scroll if user is already near bottom
        if (isAtBottom) {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
      } else {
        // For assistant messages, always scroll to show the response
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    } else if (isProcessingStarted) {
      // When processing starts, scroll to show loading indicator
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    } else if (isProcessingEnded && messages.length > 0) {
      // When processing ends and there's an assistant message, scroll to ensure it's visible
      const lastMessageIsAssistant = messages[messages.length - 1].role === 'assistant';
      if (lastMessageIsAssistant) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    } else if (messages.length > 0 && prevMessagesLengthRef.current === 0) {
      // Initial load of messages
      messagesEndRef.current?.scrollIntoView({ behavior: 'instant' as ScrollBehavior });
    }

    prevMessagesLengthRef.current = messages.length;
    prevIsAnyProcessingRef.current = isAnyProcessing;
  }, [messages, isAnyProcessing]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const messageToSend = inputMessage.trim();
    setInputMessage('');
    await sendMessage(messageToSend, voiceEnabled);
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
      setInputMessage(transcribedText);
    }
  };


  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        height: { xs: 'calc(100dvh - 140px)', md: 'calc(100vh - 200px)' },
        maxWidth: '1100px',
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
        isLoading={isAnyProcessing}
        hasMessages={messages.length > 0}
      />

      {/* Messages Container */}
      <ChatContainer ref={scrollContainerRef}>
        {messages.length === 0 ? (
          <ChatEmptyState />
        ) : (
          messages.map((msg) => (
            <ChatMessageBubble key={msg.id} role={msg.role} content={msg.content} />
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
            pb: { xs: 1, md: 0 },
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
              gap: 1.5,
              alignItems: 'flex-start',
              pl: 0.5,
            }}
          >
            <VoiceRecordButton
              isRecording={isRecording}
              isProcessing={isTranscribing}
              duration={recordedDuration}
              onStartRecording={handleStartRecording}
              onStopRecording={handleStopRecording}
              disabled={isAnyProcessing}
            />
            <ImageUploadButton
              onFileSelect={handleImageUpload}
              onError={handleImageError}
              disabled={isAnyProcessing || isRecording}
            />
            <VoiceToggle
              enabled={voiceEnabled}
              onChange={setVoiceEnabled}
              isPlaying={isAudioPlaying}
              disabled={isAnyProcessing}
            />
          </Box>

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
              mt: 1,
              pl: 2,
              width: 'fit-content',
              '& .MuiFormControlLabel-label': {
                fontSize: '0.75rem',
              },
            }}
          />
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
    </Box>
  );
};

export default ChatView;
