import React from 'react';
import { Box } from '@mui/material';

interface ChatContainerProps {
  children: React.ReactNode;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({ children }) => {
  return (
    <Box
      sx={{
        flex: 1,
        overflowY: 'auto',
        mb: 2,
        px: 2,
        '&::-webkit-scrollbar': {
          width: '8px',
        },
        '&::-webkit-scrollbar-track': {
          backgroundColor: '#2a1d3a',
          borderRadius: '4px',
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: '#9333ea',
          borderRadius: '4px',
        },
      }}
    >
      {children}
    </Box>
  );
};
