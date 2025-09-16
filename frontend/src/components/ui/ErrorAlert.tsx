import React from 'react';
import { Box, Typography, Alert } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import { AlertTriangle } from 'lucide-react';

interface ErrorAlertProps {
  message: string;
  title?: string;
  severity?: 'error' | 'warning' | 'info';
  sx?: SxProps<Theme>;
}

const ErrorAlert: React.FC<ErrorAlertProps> = ({
  message,
  title = 'Error',
  severity = 'error',
  sx = {},
}) => {
  if (severity === 'error') {
    // Custom error display for consistency with existing design
    return (
      <Box sx={{ maxWidth: '64rem', mx: 'auto', mt: 8, ...sx }}>
        <Box
          sx={{
            backgroundColor: 'rgba(220, 38, 38, 0.1)',
            border: '1px solid #dc2626',
            borderRadius: '0.75rem',
            p: 6,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <Box sx={{ flexShrink: 0 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  backgroundColor: 'rgba(220, 38, 38, 0.5)',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <AlertTriangle size={20} style={{ color: '#ef4444' }} />
              </Box>
            </Box>
            <Box sx={{ ml: 4 }}>
              <Typography
                variant="body1"
                sx={{
                  fontSize: '1.125rem',
                  fontWeight: 600,
                  color: '#ef4444',
                  mb: 1,
                }}
              >
                {title}
              </Typography>
              <Box sx={{ color: '#dc2626' }}>
                <Typography>{message}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    );
  }

  // Use MUI Alert for other severities
  return (
    <Box sx={{ maxWidth: '64rem', mx: 'auto', mt: 8, ...sx }}>
      <Alert severity={severity}>
        {message}
      </Alert>
    </Box>
  );
};

export default ErrorAlert;