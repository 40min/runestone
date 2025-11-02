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
  size = 64,
  color = 'var(--primary-color)',
  message,
  sx = {},
}) => {
  return (
    <Box
      sx={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        zIndex: 9999,
        pointerEvents: 'none',
        ...sx,
      }}
    >
      <CircularProgress size={size} sx={{ color }} />
      {message && (
        <Typography
          variant="body1"
          sx={{
            color: 'white',
            fontSize: '1.125rem',
            fontWeight: 600,
            textAlign: 'center',
          }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );
};

export default LoadingSpinner;
