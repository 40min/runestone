import React from 'react';
import { Box, Typography } from '@mui/material';
import { NewChatButton } from '../ui';

interface ChatHeaderProps {
  title: string;
  subtitle: string;
  onNewChat: () => void;
  isLoading: boolean;
  hasMessages: boolean;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  title,
  subtitle,
  onNewChat,
  isLoading,
  hasMessages,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', sm: 'row' },
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        mb: { xs: 2, md: 2 },
        gap: 2,
      }}
    >
      <Box>
        <Typography
          variant="h5"
          sx={{
            color: 'white',
            fontWeight: 'bold',
            mb: 0.5,
            fontSize: { xs: '1.25rem', md: '1.5rem' },
          }}
        >
          {title}
        </Typography>
        <Typography
          sx={{
            color: '#9ca3af',
            fontSize: { xs: '0.75rem', md: '0.875rem' },
          }}
        >
          {subtitle}
        </Typography>
      </Box>
      <NewChatButton
        onClick={onNewChat}
        isLoading={isLoading}
        hasMessages={hasMessages}
      />
    </Box>
  );
};
