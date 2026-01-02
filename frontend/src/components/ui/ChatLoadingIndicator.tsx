import React from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';

interface ChatLoadingIndicatorProps {
  message?: string;
}

export const ChatLoadingIndicator: React.FC<ChatLoadingIndicatorProps> = ({
  message = 'Teacher is typing...',
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        mb: 2,
      }}
    >
      <CircularProgress size={20} sx={{ color: '#9333ea' }} />
      <Typography sx={{ color: '#9ca3af', fontStyle: 'italic' }}>
        {message}
      </Typography>
    </Box>
  );
};
