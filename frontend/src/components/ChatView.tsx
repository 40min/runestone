import React, { useState, useRef, useEffect } from 'react';
import { Box } from '@mui/material';
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
} from './ui';
import { ImageSidebar } from './chat/ImageSidebar';
import { ChatHeader } from './chat/ChatHeader';
import { useChat } from '../hooks/useChat';
import { useChatImageUpload } from '../hooks/useChatImageUpload';

const ChatView: React.FC = () => {
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);
  const { messages, isLoading, error, sendMessage, startNewChat, refreshHistory } = useChat();
  const { uploadedImages, uploadImage, isUploading, error: uploadError } = useChatImageUpload();

  // Auto-scroll to bottom only when appropriate
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const isNewMessage = messages.length > prevMessagesLengthRef.current;
    const isUserMessage = isNewMessage && messages[messages.length - 1].role === 'user';

    // Increased threshold to 150px to be more forgiving
    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 150;

    if (isNewMessage) {
      if (isUserMessage || isAtBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    } else if (messages.length > 0 && prevMessagesLengthRef.current === 0) {
      // Initial load of messages
      messagesEndRef.current?.scrollIntoView({ behavior: 'instant' as ScrollBehavior });
    }

    prevMessagesLengthRef.current = messages.length;
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const messageToSend = inputMessage.trim();
    setInputMessage('');
    await sendMessage(messageToSend);
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
        onNewChat={startNewChat}
        isLoading={isLoading}
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

        {isLoading && <ChatLoadingIndicator />}

        {error && <ErrorAlert message={error} />}

        <div ref={messagesEndRef} />
      </ChatContainer>

        {/* Input Area */}
        <Box
          sx={{
            display: 'flex',
            gap: { xs: 1, md: 2 },
            alignItems: 'flex-end',
            pb: { xs: 1, md: 0 },
          }}
        >
          <ChatInput
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            disabled={isLoading || isUploading}
          />
          <ImageUploadButton
            onFileSelect={handleImageUpload}
            disabled={isLoading || isUploading}
          />
          <CustomButton
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isLoading || isUploading}
            sx={{
              minWidth: { xs: '48px', md: '56px' },
              height: { xs: '48px', md: '56px' },
              borderRadius: '12px',
            }}
          >
            <Send size={20} />
          </CustomButton>
        </Box>

        {/* Upload error display */}
        {uploadError && <ErrorAlert message={uploadError} sx={{ mt: 2, mb: 0 }} />}
      </Box>

      {/* Image Sidebar */}
      <ImageSidebar images={uploadedImages} />
    </Box>
  );
};

export default ChatView;
