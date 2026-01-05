import React from 'react';
import { PlusCircle } from 'lucide-react';
import CustomButton from './CustomButton';
import { Box } from '@mui/material';

interface NewChatButtonProps {
  onClick: () => void;
  isLoading: boolean;
  hasMessages: boolean;
}

export const NewChatButton: React.FC<NewChatButtonProps> = ({
  onClick,
  isLoading,
  hasMessages,
}) => {
  return (
    <Box sx={{ mt: 2, mb: 2, display: 'flex', justifyContent: 'center' }}>
      <CustomButton
        onClick={onClick}
        disabled={isLoading || !hasMessages}
        variant="secondary"
        sx={{
          borderColor: 'var(--primary-color)',
          color: 'var(--primary-color)',
          '&:hover': {
            borderColor: 'var(--primary-color)',
            backgroundColor: 'rgba(56, 224, 123, 0.1)',
          },
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 4,
          py: 1,
        }}
      >
        <PlusCircle size={18} />
        Start New Chat
      </CustomButton>
    </Box>
  );
};
