import React from 'react';
import { Box, Typography } from '@mui/material';

interface ChatMessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
}

export const ChatMessageBubble: React.FC<ChatMessageBubbleProps> = ({ role, content }) => {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: role === 'user' ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Box
        sx={{
          maxWidth: '70%',
          padding: '12px 16px',
          borderRadius: '12px',
          backgroundColor:
            role === 'user' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(58, 45, 74, 0.6)',
          border:
            role === 'user'
              ? '1px solid rgba(147, 51, 234, 0.3)'
              : '1px solid rgba(147, 51, 234, 0.1)',
        }}
      >
        <Typography
          sx={{
            color: 'white',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {content}
        </Typography>
      </Box>
    </Box>
  );
};
