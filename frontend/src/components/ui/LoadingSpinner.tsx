import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

interface LoadingSpinnerProps {
  size?: number;
  color?: string;
  message?: string;
  sx?: SxProps<Theme>;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 32,
  color = 'var(--primary-color)',
  message,
  sx = {},
}) => {
  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1,
        zIndex: 9999,
        pointerEvents: 'none',
        ...sx,
      }}
    >
      <CircularProgress size={size} sx={{ color }} />
      {message && (
        <Typography
          variant="body2"
          sx={{
            color: 'white',
            fontSize: '0.875rem',
            fontWeight: 500,
            textAlign: 'center',
            textShadow: '0 0 4px rgba(0, 0, 0, 0.5)',
          }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );
};

export default LoadingSpinner;
