import React, { useState, useRef, useEffect } from 'react';
import { Box, Typography } from '@mui/material';
import { Send } from 'lucide-react';
import {
  CustomButton,
  ErrorAlert,
  ChatMessageBubble,
  ChatEmptyState,
  ChatLoadingIndicator,
  ChatInput,
  ChatContainer,
  NewChatButton,
} from './ui';
import { useChat } from '../hooks/useChat';

const ChatView: React.FC = () => {
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { messages, isLoading, error, sendMessage, startNewChat } = useChat();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: { xs: 'calc(100dvh - 140px)', md: 'calc(100vh - 200px)' },
        maxWidth: '900px',
        margin: '0 auto',
        backgroundColor: '#1a102b',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          textAlign: 'center',
          mb: { xs: 2, md: 3 },
        }}
      >
        <Typography
          variant="h4"
          sx={{
            color: 'white',
            fontWeight: 'bold',
            mb: 1,
            fontSize: { xs: '1.5rem', md: '2.125rem' },
          }}
        >
          Chat with Your Swedish Teacher
        </Typography>
        <Typography
          sx={{
            color: '#9ca3af',
            fontSize: { xs: '0.875rem', md: '1rem' },
          }}
        >
          Ask questions about Swedish vocabulary, grammar, or practice conversation
        </Typography>
        <NewChatButton
          onClick={startNewChat}
          isLoading={isLoading}
          hasMessages={messages.length > 0}
        />
      </Box>

      {/* Messages Container */}
      <ChatContainer>
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
          disabled={isLoading}
        />
        <CustomButton
          onClick={handleSendMessage}
          disabled={!inputMessage.trim() || isLoading}
          sx={{
            minWidth: { xs: '48px', md: '56px' },
            height: { xs: '48px', md: '56px' },
            borderRadius: '12px',
          }}
        >
          <Send size={20} />
        </CustomButton>
      </Box>
    </Box>
  );
};

export default ChatView;
