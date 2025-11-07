import React from 'react';
import { Button, CircularProgress } from '@mui/material';

interface AuthButtonProps {
  loading?: boolean;
  children: React.ReactNode;
  onClick?: (e: React.FormEvent) => void;
  type?: 'submit' | 'button';
  variant?: 'primary' | 'secondary';
  loadingText?: string;
}

const AuthButton: React.FC<AuthButtonProps> = ({
  loading = false,
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  loadingText,
}) => {
  const getSx = () => {
    if (variant === 'primary') {
      return {
        mt: 2,
        padding: '10px 20px',
        backgroundColor: 'var(--primary-color)',
        color: 'white',
        border: 'none',
        borderRadius: '6px',
        cursor: loading ? 'not-allowed' : 'pointer',
        fontSize: '14px',
        fontWeight: 'bold',
        opacity: loading ? 0.6 : 1,
        '&:hover': {
          opacity: 0.9,
        },
      };
    }
    // secondary variant
    return {
      mt: 2,
      padding: '10px 20px',
      backgroundColor: 'transparent',
      color: '#9ca3af',
      border: 'none',
      borderRadius: '6px',
      cursor: loading ? 'not-allowed' : 'pointer',
      fontSize: '14px',
      fontWeight: 'bold',
      opacity: loading ? 0.6 : 1,
      '&:hover': {
        color: 'white',
        backgroundColor: 'rgba(156, 163, 175, 0.1)',
      },
    };
  };

  return (
    <Button
      type={type}
      onClick={onClick}
      disabled={loading}
      sx={getSx()}
    >
      {loading ? (
        <>
          <CircularProgress size={24} sx={{ mr: 1, color: variant === 'primary' ? 'white' : '#9ca3af' }} />
          {loadingText || 'Loading...'}
        </>
      ) : (
        children
      )}
    </Button>
  );
};

export default AuthButton;
