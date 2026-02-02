import React from 'react';
import { FormControlLabel, Switch, Tooltip, Box } from '@mui/material';
import { VolumeUp, VolumeOff } from '@mui/icons-material';

interface VoiceToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  isPlaying?: boolean;
  disabled?: boolean;
}

/**
 * A toggle switch to enable or disable voice replies.
 */
export const VoiceToggle: React.FC<VoiceToggleProps> = ({
  enabled,
  onChange,
  isPlaying = false,
  disabled = false,
}) => {
  return (
    <Box sx={{
      display: 'flex',
      alignItems: 'center',
      '@keyframes pulse': {
        '0%': { opacity: 1, transform: 'scale(1)' },
        '50%': { opacity: 0.6, transform: 'scale(1.1)' },
        '100%': { opacity: 1, transform: 'scale(1)' },
      }
    }}>
      <Tooltip title={enabled ? "Disable voice replies" : "Enable voice replies"}>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={enabled}
              onChange={(e) => onChange(e.target.checked)}
              disabled={disabled}
              color="primary"
            />
          }
          label={
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              color: enabled ? (isPlaying ? 'secondary.main' : 'primary.main') : '#9ca3af',
              animation: isPlaying ? 'pulse 1.5s infinite ease-in-out' : 'none'
            }}>
              {enabled ? (isPlaying ? <VolumeUp fontSize="small" /> : <VolumeUp fontSize="small" />) : <VolumeOff fontSize="small" />}
              <Box component="span" sx={{ fontSize: '0.875rem', fontWeight: 500 }}>
                {isPlaying ? 'Speaking...' : 'Voice'}
              </Box>
            </Box>
          }
          sx={{ ml: 0, mr: 0 }}
        />
      </Tooltip>
    </Box>
  );
};
