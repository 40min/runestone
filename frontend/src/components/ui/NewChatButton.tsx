import React from 'react';
import { PlusCircle } from 'lucide-react';
import CustomButton from './CustomButton';

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
        px: 2, // Reduced from 4
        py: 0.5, // Reduced from 1
        fontSize: '0.875rem', // Smaller text
      }}
    >
      <PlusCircle size={16} />
      Start New Chat
    </CustomButton>
  );
};
