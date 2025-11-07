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
        return <CheckCircle sx={{ color: '#10b981' }} />;
      case 'error':
        return <Error sx={{ color: '#ef4444' }} />;
      case 'warning':
        return <Warning sx={{ color: '#f59e0b' }} />;
      case 'info':
      default:
        return <Info sx={{ color: '#3b82f6' }} />;
    }
  };

  const getBackgroundColor = () => {
    switch (severity) {
      case 'success':
        return 'rgba(16, 185, 129, 0.1)';
      case 'error':
        return 'rgba(239, 68, 68, 0.1)';
      case 'warning':
        return 'rgba(245, 158, 11, 0.1)';
      case 'info':
      default:
        return 'rgba(59, 130, 246, 0.1)';
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
        top: 24,
        right: 24,
        zIndex: 1400,
        maxWidth: { xs: '90vw', sm: '80vw', md: '500px' },
        minWidth: '300px',
      }}
    >
      <Slide direction="left" in={visible} mountOnEnter unmountOnExit>
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
                color: '#1f2937',
                lineHeight: 1.4,
                fontSize: '0.875rem',
              }}
            >
              {message}
            </Typography>
          </Box>
          <IconButton
            size="small"
            onClick={handleClose}
            sx={{
              color: '#6b7280',
              '&:hover': {
                color: '#374151',
                backgroundColor: 'rgba(0, 0, 0, 0.04)',
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
