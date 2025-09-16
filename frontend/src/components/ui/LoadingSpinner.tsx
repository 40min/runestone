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
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        py: 8,
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