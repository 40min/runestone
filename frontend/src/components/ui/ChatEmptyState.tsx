import React from 'react';
import { Box, Typography } from '@mui/material';
import { MessageCircle } from 'lucide-react';

interface ChatEmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
}

export const ChatEmptyState: React.FC<ChatEmptyStateProps> = ({
  title = 'Start a conversation',
  description = 'Ask me anything about Swedish! I\'m here to help you learn vocabulary, understand grammar, or practice conversation.',
  icon,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: '#6b7280',
      }}
    >
      {icon || <MessageCircle size={64} style={{ marginBottom: '16px', opacity: 0.5 }} />}
      <Typography variant="h6" sx={{ mb: 1 }}>
        {title}
      </Typography>
      <Typography sx={{ textAlign: 'center', maxWidth: '400px' }}>
        {description}
      </Typography>
    </Box>
  );
};
