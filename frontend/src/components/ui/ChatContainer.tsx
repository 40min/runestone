import React from 'react';
import { Box } from '@mui/material';
import { chatPanelSx } from '../chat/chatStyles';

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
          ...chatPanelSx,
          flex: 1,
          overflowY: 'auto',
          mb: 0,
          px: { xs: 2, md: 4 },
          py: { xs: 2, md: 3 },
          minHeight: 0,
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: 'rgba(9, 19, 52, 0.8)',
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'rgba(80, 111, 186, 0.72)',
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
