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
          backgroundColor: 'rgba(8, 18, 50, 0.78)',
          borderRadius: '8px',
          minHeight: '46px',
          '& fieldset': {
            borderColor: 'rgba(99, 114, 173, 0.42)',
          },
          '&:hover fieldset': {
            borderColor: 'rgba(112, 139, 210, 0.68)',
          },
          '&.Mui-focused fieldset': {
            borderColor: '#638bd8',
          },
        },
        '& .MuiInputBase-input::placeholder': {
          color: '#9ca3af',
          opacity: 1,
        },
        '& .MuiInputBase-input': {
          py: 0.25,
        },
        ...props.sx,
      }}
    />
  );
};
