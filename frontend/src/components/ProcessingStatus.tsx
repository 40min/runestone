import React from 'react';
import { Box, Typography } from '@mui/material';

interface ProcessingStatusProps {
  isProcessing: boolean;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ isProcessing }) => {
  if (!isProcessing) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        py: 8,
      }}
    >
      <Box
        sx={{
          position: 'relative',
          width: 64,
          height: 64,
        }}
      >
        <Box
          sx={{
            width: '100%',
            height: '100%',
            border: '4px solid #4d3c63',
            borderTop: '4px solid var(--primary-color)',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            '@keyframes spin': {
              '0%': { transform: 'rotate(0deg)' },
              '100%': { transform: 'rotate(360deg)' },
            },
          }}
          role="status"
          aria-label="Processing"
        />
      </Box>
      <Typography
        variant="body1"
        sx={{
          fontSize: '1.125rem',
          fontWeight: 600,
          color: 'white',
        }}
      >
        Processing...
      </Typography>
    </Box>
  );
};

export default ProcessingStatus;