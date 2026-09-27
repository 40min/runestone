import React from 'react';
import { Box, Typography } from '@mui/material';

interface ChatLoadingIndicatorProps {
  message?: string;
}

export const ChatLoadingIndicator: React.FC<ChatLoadingIndicatorProps> = ({
  message = 'Teacher is typing...',
}) => {
  return (
    <Box
      data-testid="loading-indicator"
      role="status"
      aria-live="polite"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 1.25,
        mb: 2,
        px: 1.5,
        py: 0.75,
        borderRadius: 2,
        border: '1px solid rgba(99, 114, 173, 0.35)',
        backgroundColor: 'rgba(8, 18, 50, 0.65)',
        '@keyframes thinkingPulse': {
          '0%, 60%, 100%': { opacity: 0.35, transform: 'translateY(0)' },
          '30%': { opacity: 1, transform: 'translateY(-3px)' },
        },
      }}
    >
      <Box aria-hidden="true" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {[0, 1, 2].map((index) => (
          <Box
            key={index}
            sx={{
              width: 5,
              height: 5,
              borderRadius: '50%',
              backgroundColor: 'var(--primary-color)',
              animation: 'thinkingPulse 1.2s ease-in-out infinite',
              animationDelay: `${index * 0.16}s`,
              '@media (prefers-reduced-motion: reduce)': {
                animation: 'none',
                opacity: 0.8,
              },
            }}
          />
        ))}
      </Box>
      <Typography sx={{ color: '#aeb8cc', fontSize: '0.83rem' }}>
        {message}
      </Typography>
    </Box>
  );
};
