import React from 'react';
import { Box } from '@mui/material';

interface ChatContainerProps {
  children: React.ReactNode;
  ref?: React.Ref<HTMLDivElement>;
}

export const ChatContainer = React.forwardRef<HTMLDivElement, ChatContainerProps>(
  ({ children }, ref) => {
    return (
      <Box
        ref={ref}
        sx={{
          flex: 1,
          overflowY: 'auto',
          mb: 0,
          px: { xs: 2, md: 4 },
          py: { xs: 2, md: 3 },
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
  }
);

ChatContainer.displayName = 'ChatContainer';
