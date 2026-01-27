import React, { useEffect, useState, useCallback } from 'react';
import { Box, Typography, IconButton, Slide } from '@mui/material';
import { Close, CheckCircle, Error, Warning, Info } from '@mui/icons-material';

interface SnackbarProps {
  message: string;
  severity?: 'success' | 'error' | 'warning' | 'info';
  autoHideDuration?: number;
  onClose?: () => void;
  open: boolean;
}

const Snackbar: React.FC<SnackbarProps> = ({
  message,
  severity = 'info',
  autoHideDuration = 6000,
  onClose,
  open,
}) => {
  const [visible, setVisible] = useState(false);

  const handleClose = useCallback(() => {
    setVisible(false);
    setTimeout(() => {
      onClose?.();
    }, 300); // Allow time for slide animation
  }, [onClose]);

  useEffect(() => {
    setVisible(open);
    if (open && autoHideDuration > 0) {
      const timer = setTimeout(() => {
        handleClose();
      }, autoHideDuration);
      return () => clearTimeout(timer);
    }
  }, [open, autoHideDuration, handleClose]);

  const getIcon = () => {
    switch (severity) {
      case 'success':
        return <CheckCircle sx={{ color: '#34d399' }} />; // Lighter Emerald
      case 'error':
        return <Error sx={{ color: '#fca5a5' }} />; // Lighter Red
      case 'warning':
        return <Warning sx={{ color: '#fcd34d' }} />; // Lighter Amber
      case 'info':
      default:
        return <Info sx={{ color: '#93c5fd' }} />; // Lighter Blue
    }
  };

  const getBackgroundColor = () => {
    switch (severity) {
      case 'success':
        return '#064e3b'; // Dark Emerald
      case 'error':
        return '#7f1d1d'; // Dark Red
      case 'warning':
        return '#78350f'; // Dark Amber
      case 'info':
      default:
        return '#1e3a8a'; // Dark Blue
    }
  };

  const getBorderColor = () => {
    switch (severity) {
      case 'success':
        return '#10b981';
      case 'error':
        return '#ef4444';
      case 'warning':
        return '#f59e0b';
      case 'info':
      default:
        return '#3b82f6';
    }
  };

  if (!visible) return null;

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: { xs: 16, sm: 24 },
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 2000,
        maxWidth: { xs: '95vw', sm: '80vw', md: '500px' },
        minWidth: { xs: 'calc(100vw - 32px)', sm: '350px' },
      }}
    >
      <Slide direction="up" in={visible} mountOnEnter unmountOnExit>
        <Box
          sx={{
            backgroundColor: getBackgroundColor(),
            border: `1px solid ${getBorderColor()}`,
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            p: 2,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 2,
            wordWrap: 'break-word',
            overflowWrap: 'break-word',
            transition: 'all 0.3s ease-in-out',
          }}
        >
          {getIcon()}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="body2"
              sx={{
                color: '#ffffff',
                lineHeight: 1.5,
                fontSize: '0.875rem',
                fontWeight: 500,
              }}
            >
              {message}
            </Typography>
          </Box>
          <IconButton
            size="small"
            onClick={handleClose}
            sx={{
              color: 'rgba(255, 255, 255, 0.7)',
              '&:hover': {
                color: '#ffffff',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
              },
            }}
          >
            <Close fontSize="small" />
          </IconButton>
        </Box>
      </Slide>
    </Box>
  );
};

export default Snackbar;
