import React, { useEffect, useMemo, useRef, useState } from "react";
import { ExpandLess, ExpandMore } from "@mui/icons-material";
import { Box, ButtonBase, Collapse, Typography } from "@mui/material";
import {
  ErrorAlert,
  ChatMessageBubble,
  ChatEmptyState,
  ChatLoadingIndicator,
  ChatContainer,
  Snackbar,
} from "./ui";
import { ChatComposerControls } from "./chat/ChatComposerControls";
import { ChatComposerInputRow } from "./chat/ChatComposerInputRow";
import { ImageSidebar } from "./chat/ImageSidebar";
import { ChatHeader } from "./chat/ChatHeader";
import { ChatPlaybackSettings } from "./chat/ChatPlaybackSettings";
import AgentMemoryModal from "./chat/AgentMemoryModal";
import { useChat } from "../hooks/useChat";
import { useChatImageUpload } from "../hooks/useChatImageUpload";
import { useVoiceRecording } from "../hooks/useVoiceRecording";
import { useAudioPlayback } from "../hooks/useAudioPlayback";
import { useAuth } from "../context/AuthContext";
import { LANGUAGES } from "../constants";
import { appendTranscribedTextToInput } from "../utils/chatInputText";

const IMPROVE_TRANSCRIPTION_KEY = "runestone_improve_transcription";
const VOICE_ENABLED_KEY = "runestone_voice_enabled";
const SPEECH_SPEED_KEY = "runestone_speech_speed";
const AUTOSEND_KEY = "runestone_autosend";
const STT_LANGUAGE_KEY = "runestone_stt_language";

const getSupportedSpeechLanguage = (language?: string | null) =>
  language && LANGUAGES.includes(language as (typeof LANGUAGES)[number])
    ? language
    : null;

const buildStudentAvatarLabel = (
  name?: string | null,
  surname?: string | null,
): string => {
  const first = name?.trim().charAt(0) ?? "";
  const last = surname?.trim().charAt(0) ?? "";
  const initials = `${first}${last}`.trim().toUpperCase();
  return initials || "You";
};

const ChatView: React.FC = () => {
  const [inputMessage, setInputMessage] = useState("");
  const { userData } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastMessageRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);
  const prevIsAnyProcessingRef = useRef(false);
  const {
    messages,
    isLoading,
    isSyncingHistory,
    historySyncNotice,
    isBackendAvailable,
    error,
    sendMessage,
    startNewChat,
    refreshHistory,
  } = useChat();
  const {
    uploadedImages,
    uploadImage,
    isUploading,
    error: uploadError,
    clearImages,
  } = useChatImageUpload();
  const [snackbarError, setSnackbarError] = useState<string | null>(null);
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
  const [areComposerControlsExpanded, setAreComposerControlsExpanded] =
    useState(false);

  // Voice recording with improve option
  const [improveTranscription, setImproveTranscription] = useState(() => {
    const stored = localStorage.getItem(IMPROVE_TRANSCRIPTION_KEY);
    return stored === null ? true : stored === "true";
  });

  const [voiceEnabled, setVoiceEnabled] = useState(() => {
    const stored = localStorage.getItem(VOICE_ENABLED_KEY);
    return stored === "true";
  });

  const [speechSpeed, setSpeechSpeed] = useState(() => {
    const stored = localStorage.getItem(SPEECH_SPEED_KEY);
    return stored && Number.isFinite(Number(stored)) ? Number(stored) : 1.1;
  });

  const [autoSend, setAutoSend] = useState(() => {
    const stored = localStorage.getItem(AUTOSEND_KEY);
    return stored === null ? false : stored === "true";
  });

  const [speechLanguage, setSpeechLanguage] = useState(() => {
    const stored = getSupportedSpeechLanguage(
      localStorage.getItem(STT_LANGUAGE_KEY),
    );
    const profileLanguage = getSupportedSpeechLanguage(userData?.mother_tongue);
    return stored ?? profileLanguage ?? "Swedish";
  });
  const [hasSpeechLanguageOverride, setHasSpeechLanguageOverride] = useState(
    () => getSupportedSpeechLanguage(localStorage.getItem(STT_LANGUAGE_KEY)) !== null,
  );

  const {
    isRecording,
    isProcessing: isTranscribing,
    recordedDuration,
    startRecording,
    stopRecording,
    error: voiceError,
    clearError: clearVoiceError,
  } = useVoiceRecording(improveTranscription, speechLanguage);

  const {
    isPlaying: isAudioPlaying,
    canReplay,
    playbackMessageId,
    pendingMessageId,
    play,
    pause,
    replayLast,
    setExpectedMessageId,
    clearPlayback,
  } = useAudioPlayback(voiceEnabled);

  const canUseMicrophone =
    typeof window !== "undefined" &&
    window.isSecureContext &&
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined";

  // Do not include background history polling here, otherwise the scroll effect
  // reacts on every poll cycle even when no new messages arrived.
  const isAnyProcessing =
    isLoading || isUploading || isTranscribing || isSyncingHistory;
  const lastAssistantMessageId = (() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role === "assistant") {
        return message.id;
      }
    }
    return null;
  })();
  const latestTeacherEmotion = (() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role === "assistant") {
        return message.teacherEmotion;
      }
    }
    return undefined;
  })();
  const lastUserMessageId = (() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role === "user") {
        return message.id;
      }
    }
    return null;
  })();
  const studentAvatarLabel = useMemo(
    () => buildStudentAvatarLabel(userData?.name, userData?.surname),
    [userData?.name, userData?.surname],
  );

  const scrollToLastMessage = (
    behavior: ScrollBehavior,
    block: ScrollLogicalPosition,
  ) => {
    lastMessageRef.current?.scrollIntoView({
      behavior,
      block,
      inline: "nearest",
    });
  };

  // Persist settings
  useEffect(() => {
    localStorage.setItem(
      IMPROVE_TRANSCRIPTION_KEY,
      String(improveTranscription),
    );
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

  useEffect(() => {
    localStorage.setItem(STT_LANGUAGE_KEY, speechLanguage);
  }, [speechLanguage]);

  useEffect(() => {
    if (hasSpeechLanguageOverride) {
      return;
    }

    const profileLanguage = getSupportedSpeechLanguage(userData?.mother_tongue);
    if (profileLanguage && profileLanguage !== speechLanguage) {
      setSpeechLanguage(profileLanguage);
    }
  }, [userData?.mother_tongue, speechLanguage, hasSpeechLanguageOverride]);

  // Show voice errors in snackbar
  useEffect(() => {
    if (voiceError) {
      setSnackbarError(voiceError);
      clearVoiceError();
    }
  }, [voiceError, clearVoiceError]);

  useEffect(() => {
    if (isRecording) {
      setAreComposerControlsExpanded(true);
    }
  }, [isRecording]);

  // Auto-scroll to bottom when messages change or loading state changes
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const isInitialLoad =
      messages.length > 0 && prevMessagesLengthRef.current === 0;
    const isNewMessage = messages.length > prevMessagesLengthRef.current;
    const isProcessingStarted =
      isAnyProcessing && !prevIsAnyProcessingRef.current;
    const isProcessingEnded =
      !isAnyProcessing && prevIsAnyProcessingRef.current;

    // For user messages, only scroll if near bottom to avoid disrupting reading
    // For assistant messages, always scroll to show the response
    const isAtBottom =
      container.scrollHeight - container.scrollTop <=
      container.clientHeight + 150;

    if (isInitialLoad) {
      // Initial load of messages (e.g. switching back to Chat tab / history refresh)
      scrollToLastMessage("auto", "start");
    } else if (isNewMessage) {
      const isUserMessage = messages[messages.length - 1].role === "user";
      if (isUserMessage) {
        // For user messages, only scroll if user is already near bottom
        if (isAtBottom) {
          scrollToLastMessage("smooth", "end");
        }
      } else {
        // For assistant messages, always scroll to the beginning of the response
        scrollToLastMessage("smooth", "start");
      }
    } else if (isProcessingStarted) {
      // When processing starts, scroll to show loading indicator
      if (isAtBottom) {
        messagesEndRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "end",
          inline: "nearest",
        });
      }
    } else if (isProcessingEnded && messages.length > 0) {
      // When processing ends and there's an assistant message, scroll to ensure it's visible
      const lastMessageIsAssistant =
        messages[messages.length - 1].role === "assistant";
      if (lastMessageIsAssistant) {
        scrollToLastMessage("smooth", "start");
      }
    }

    prevMessagesLengthRef.current = messages.length;
    prevIsAnyProcessingRef.current = isAnyProcessing;
  }, [messages, isAnyProcessing]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const messageToSend = inputMessage.trim();
    setInputMessage("");
    const assistantMessageId = await sendMessage(
      messageToSend,
      voiceEnabled,
      speechSpeed,
    );
    if (voiceEnabled && assistantMessageId) {
      setExpectedMessageId(assistantMessageId);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
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
    clearPlayback();
  };

  const handleStartRecording = async () => {
    await startRecording();
  };

  const handleStopRecording = async () => {
    const transcribedText = await stopRecording();
    if (transcribedText) {
      if (autoSend) {
        const assistantMessageId = await sendMessage(
          transcribedText,
          voiceEnabled,
          speechSpeed,
        );
        if (voiceEnabled && assistantMessageId) {
          setExpectedMessageId(assistantMessageId);
        }
      } else {
        setInputMessage((currentInput) =>
          appendTranscribedTextToInput(currentInput, transcribedText),
        );
      }
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "row",
        height: { xs: "calc(100dvh - 58px)", md: "calc(100vh - 74px)" },
        width: "100%",
        maxWidth: { xs: "100%", md: "100%" },
        margin: "0 auto",
        backgroundColor: "#1a102b",
        gap: 2,
      }}
    >
      {/* Main chat area */}
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
        }}
      >
        {/* Header */}
        <ChatHeader
          onNewChat={handleNewChat}
          onOpenMemory={() => setIsMemoryModalOpen(true)}
          isLoading={isAnyProcessing}
          hasMessages={messages.length > 0}
          isBackendAvailable={isBackendAvailable}
          teacherEmotion={latestTeacherEmotion}
        />

        {/* Messages Container */}
        <ChatContainer ref={scrollContainerRef}>
          {messages.length === 0 ? (
            <ChatEmptyState />
          ) : (
            messages.map((msg, index) => (
              <div
                key={msg.id}
                ref={index === messages.length - 1 ? lastMessageRef : undefined}
              >
                <ChatMessageBubble
                  role={msg.role}
                  content={msg.content}
                  sources={msg.sources}
                  teacherEmotion={msg.teacherEmotion}
                  responseTimeMs={msg.responseTimeMs}
                  createdAt={msg.createdAt}
                  isLast={index === messages.length - 1}
                  isLatestByRole={
                    (msg.role === "assistant" && msg.id === lastAssistantMessageId) ||
                    (msg.role === "user" && msg.id === lastUserMessageId)
                  }
                  showAudioControls={
                    msg.role === "assistant" &&
                    msg.id === lastAssistantMessageId &&
                    (msg.id === playbackMessageId || msg.id === pendingMessageId)
                  }
                  isAudioPlaying={msg.id === playbackMessageId && isAudioPlaying}
                  canReplayAudio={msg.id === playbackMessageId && canReplay}
                  onPlayAudio={() => {
                    void play();
                  }}
                  onPauseAudio={pause}
                  onReplayAudio={() => {
                    void replayLast();
                  }}
                  studentAvatarLabel={studentAvatarLabel}
                />
              </div>
            ))
          )}

          {isLoading && (
            <ChatLoadingIndicator message="Teacher is thinking..." />
          )}
          {isUploading && <ChatLoadingIndicator message="Analyzing image..." />}
          {isTranscribing && (
            <ChatLoadingIndicator message="Transcribing voice..." />
          )}
          {isSyncingHistory && (
            <ChatLoadingIndicator message="Syncing older messages..." />
          )}

          {error && <ErrorAlert message={error} />}
          {historySyncNotice && (
            <Box
              sx={{
                border: "1px solid rgba(245, 158, 11, 0.5)",
                backgroundColor: "rgba(245, 158, 11, 0.1)",
                borderRadius: 1,
                p: 1.25,
                mt: 1,
              }}
            >
              <Typography variant="body2" sx={{ color: "#fbbf24" }}>
                {historySyncNotice}
              </Typography>
            </Box>
          )}

          <div ref={messagesEndRef} />
        </ChatContainer>

        {/* Input Area */}
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 1,
            px: { xs: 2, md: 4 },
            pt: { xs: 1.5, md: 2 },
            pb: { xs: "calc(12px + env(safe-area-inset-bottom))", md: 2 },
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            backgroundColor: "rgba(26, 16, 43, 0.96)",
          }}
        >
          <ChatComposerInputRow
            inputMessage={inputMessage}
            isAnyProcessing={isAnyProcessing}
            isRecording={isRecording}
            onInputChange={setInputMessage}
            onKeyPress={handleKeyPress}
            onSendMessage={handleSendMessage}
          />

          <Box
            sx={{
              position: "relative",
              mt: 2.5,
              pt: areComposerControlsExpanded ? 1.75 : 0,
            }}
          >
            <ButtonBase
              onClick={() =>
                setAreComposerControlsExpanded((expanded) => !expanded)
              }
              disabled={isRecording}
              aria-expanded={areComposerControlsExpanded}
              aria-controls="teacher-chat-controls-panel"
              aria-label={areComposerControlsExpanded ? "Hide chat controls" : "Show chat controls"}
              sx={{
                position: "absolute",
                top: 0,
                left: "50%",
                transform: "translate(-50%, -50%)",
                zIndex: 1,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                minWidth: 72,
                gap: 0.5,
                px: 1.65,
                py: 0.4,
                borderRadius: 999,
                border: "1px solid rgba(164, 92, 255, 0.55)",
                background:
                  areComposerControlsExpanded
                    ? "linear-gradient(180deg, rgba(101, 34, 188, 0.92) 0%, rgba(54, 22, 103, 0.96) 100%)"
                    : "linear-gradient(180deg, rgba(41, 18, 79, 0.98) 0%, rgba(26, 14, 51, 0.98) 100%)",
                boxShadow: areComposerControlsExpanded
                  ? "0 0 0 1px rgba(192, 132, 252, 0.15), 0 10px 30px rgba(126, 34, 206, 0.4)"
                  : "0 8px 24px rgba(10, 6, 24, 0.42)",
                color: "#f5f3ff",
                transition:
                  "transform 180ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease",
                "&:hover": {
                  transform: "translate(-50%, -50%) scale(1.03)",
                  boxShadow: "0 0 0 1px rgba(216, 180, 254, 0.22), 0 12px 34px rgba(126, 34, 206, 0.46)",
                },
                "&:focus-visible": {
                  outline: "none",
                  transform: "translate(-50%, -50%) scale(1.03)",
                  boxShadow: "0 0 0 2px rgba(243, 232, 255, 0.72), 0 0 0 5px rgba(126, 34, 206, 0.22), 0 12px 34px rgba(126, 34, 206, 0.46)",
                },
                "&.Mui-disabled": {
                  opacity: 0.58,
                  color: "#c4b5fd",
                  cursor: "not-allowed",
                },
              }}
            >
              {areComposerControlsExpanded ? (
                <ExpandLess fontSize="small" />
              ) : (
                <ExpandMore fontSize="small" />
              )}
            </ButtonBase>

            <Collapse
              in={areComposerControlsExpanded}
              id="teacher-chat-controls-panel"
              unmountOnExit
            >
              <Box
                sx={{
                  px: { xs: 1.25, md: 1.5 },
                  pb: 1.25,
                  pt: 1.1,
                  borderRadius: 2.5,
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  background:
                    "radial-gradient(circle at top center, rgba(111, 34, 178, 0.18) 0%, rgba(255, 255, 255, 0.03) 42%, rgba(255, 255, 255, 0.02) 100%)",
                  boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 18px 40px rgba(8, 5, 20, 0.22)",
                }}
              >
                <Typography
                  sx={{
                    mb: 1.15,
                    color: "#9ca3af",
                    fontSize: "0.72rem",
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                  }}
                >
                  Voice, image, and transcription settings
                </Typography>

                <ChatComposerControls
                  isAnyProcessing={isAnyProcessing}
                  isRecording={isRecording}
                  canUseMicrophone={canUseMicrophone}
                  isTranscribing={isTranscribing}
                  recordedDuration={recordedDuration}
                  autoSend={autoSend}
                  improveTranscription={improveTranscription}
                  speechLanguage={speechLanguage}
                  languages={LANGUAGES}
                  onImageUpload={handleImageUpload}
                  onImageError={handleImageError}
                  onStartRecording={handleStartRecording}
                  onStopRecording={handleStopRecording}
                  onAutoSendChange={setAutoSend}
                  onImproveTranscriptionChange={setImproveTranscription}
                  onSpeechLanguageChange={(value) => {
                    setHasSpeechLanguageOverride(true);
                    setSpeechLanguage(value);
                  }}
                />

                <ChatPlaybackSettings
                  voiceEnabled={voiceEnabled}
                  isAudioPlaying={isAudioPlaying}
                  isAnyProcessing={isAnyProcessing}
                  speechSpeed={speechSpeed}
                  onVoiceEnabledChange={setVoiceEnabled}
                  onSpeechSpeedChange={setSpeechSpeed}
                />
              </Box>
            </Collapse>
          </Box>
        </Box>

        {/* Upload error display */}
        {uploadError && (
          <ErrorAlert message={uploadError} sx={{ mt: 2, mb: 0 }} />
        )}
      </Box>

      {/* Image Sidebar */}
      <ImageSidebar images={uploadedImages} />

      {/* Validation Error Snackbar */}
      <Snackbar
        open={!!snackbarError}
        message={snackbarError || ""}
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
