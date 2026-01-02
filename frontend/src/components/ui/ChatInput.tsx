import React from 'react';
import { TextField, type TextFieldProps } from '@mui/material';

type ChatInputProps = Omit<TextFieldProps, 'variant'>;

export const ChatInput: React.FC<ChatInputProps> = (props) => {
  return (
    <TextField
      fullWidth
      multiline
      maxRows={4}
      {...props}
      sx={{
        '& .MuiOutlinedInput-root': {
          color: 'white',
          backgroundColor: 'rgba(58, 45, 74, 0.4)',
          borderRadius: '12px',
          '& fieldset': {
            borderColor: 'rgba(147, 51, 234, 0.3)',
          },
          '&:hover fieldset': {
            borderColor: 'rgba(147, 51, 234, 0.5)',
          },
          '&.Mui-focused fieldset': {
            borderColor: '#9333ea',
          },
        },
        '& .MuiInputBase-input::placeholder': {
          color: '#9ca3af',
          opacity: 1,
        },
        ...props.sx,
      }}
    />
  );
};
