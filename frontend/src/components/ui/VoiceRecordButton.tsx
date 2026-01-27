import React from 'react';
import { Mic, Square } from 'lucide-react';
import { Box, CircularProgress, keyframes } from '@mui/material';
import CustomButton from './CustomButton';

interface VoiceRecordButtonProps {
  isRecording: boolean;
  isProcessing: boolean;
  duration: number;
  onStartRecording: () => void;
  onStopRecording: () => void;
  disabled?: boolean;
}

// Pulsing animation for recording state
const pulse = keyframes`
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
`;

const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const VoiceRecordButton: React.FC<VoiceRecordButtonProps> = ({
  isRecording,
  isProcessing,
  duration,
  onStartRecording,
  onStopRecording,
  disabled = false,
}) => {
  const handleClick = () => {
    if (isRecording) {
      onStopRecording();
    } else {
      onStartRecording();
    }
  };

  // Show processing spinner
  if (isProcessing) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: { xs: '48px', md: '56px' },
          height: { xs: '48px', md: '56px' },
        }}
      >
        <CircularProgress size={24} sx={{ color: 'var(--primary-color)' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {isRecording && (
        <Box
          sx={{
            color: '#ef4444',
            fontSize: '0.875rem',
            fontWeight: 500,
            minWidth: '45px',
          }}
        >
          {formatDuration(duration)}
        </Box>
      )}
      <CustomButton
        onClick={handleClick}
        disabled={disabled || isProcessing}
        sx={{
          minWidth: { xs: '48px', md: '56px' },
          height: { xs: '48px', md: '56px' },
          borderRadius: '12px',
          ...(isRecording && {
            backgroundColor: '#ef4444',
            animation: `${pulse} 2s infinite`,
            '&:hover': {
              backgroundColor: '#dc2626',
            },
          }),
        }}
      >
        {isRecording ? <Square size={20} /> : <Mic size={20} />}
      </CustomButton>
    </Box>
  );
};

export default VoiceRecordButton;
