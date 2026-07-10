import React from 'react';
import { Button, CircularProgress } from '@mui/material';

interface AuthButtonProps {
  loading?: boolean;
  children: React.ReactNode;
  onClick?: (e: React.FormEvent) => void;
  type?: 'submit' | 'button';
  variant?: 'primary' | 'secondary';
  loadingText?: string;
  fullWidth?: boolean;
}

const AuthButton: React.FC<AuthButtonProps> = ({
  loading = false,
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  loadingText,
  fullWidth = true,
}) => {
  const primarySx = {
    backgroundColor: '#38e07b',
    color: '#0a1a10',
    fontWeight: 700,
    fontSize: '0.875rem',
    letterSpacing: '0.08em',
    textTransform: 'uppercase' as const,
    borderRadius: '10px',
    py: 1.75,
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.7 : 1,
    boxShadow: loading ? 'none' : '0 4px 20px rgba(56,224,123,0.35)',
    '&:hover': {
      backgroundColor: '#2ecc6e',
      boxShadow: '0 6px 24px rgba(56,224,123,0.5)',
    },
    '&:active': { transform: 'scale(0.98)' },
    '&.Mui-disabled': { backgroundColor: '#38e07b', color: '#0a1a10', opacity: 0.55 },
  };

  const secondarySx = {
    backgroundColor: 'transparent',
    color: '#9ca3af',
    fontWeight: 500,
    fontSize: '0.875rem',
    textTransform: 'none' as const,
    borderRadius: '8px',
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.6 : 1,
    '&:hover': { color: 'white', backgroundColor: 'rgba(156,163,175,0.08)' },
  };

  const sx = variant === 'primary' ? primarySx : secondarySx;

  return (
    <Button
      type={type}
      onClick={onClick}
      disabled={loading}
      fullWidth={fullWidth}
      sx={sx}
    >
      {loading ? (
        <>
          <CircularProgress
            size={18}
            sx={{ mr: 1, color: variant === 'primary' ? '#0a1a10' : '#9ca3af' }}
          />
          {loadingText || 'Loading...'}
        </>
      ) : (
        children
      )}
    </Button>
  );
};

export default AuthButton;
