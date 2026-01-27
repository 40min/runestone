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
          minWidth: '40px',
          height: '40px',
        }}
      >
        <CircularProgress size={20} sx={{ color: 'var(--primary-color)' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {isRecording && (
        <Box
          sx={{
            color: '#ef4444',
            fontSize: '0.75rem',
            fontWeight: 500,
            minWidth: '35px',
          }}
        >
          {formatDuration(duration)}
        </Box>
      )}
      <CustomButton
        onClick={handleClick}
        disabled={disabled || isProcessing}
        variant="secondary"
        sx={{
          minWidth: '40px',
          height: '40px',
          width: '40px',
          borderRadius: '10px',
          backgroundColor: isRecording ? '#ef4444' : 'rgba(255, 255, 255, 0.05)',
          color: isRecording ? 'white' : '#9ca3af',
          p: 0,
          ...(isRecording && {
            animation: `${pulse} 2s infinite`,
            '&:hover': {
              backgroundColor: '#dc2626',
            },
          }),
          ...(!isRecording && {
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              color: 'white',
            },
          }),
        }}
        size="small"
      >
        {isRecording ? <Square size={16} /> : <Mic size={18} />}
      </CustomButton>
    </Box>
  );
};

export default VoiceRecordButton;
