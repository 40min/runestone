import React from "react";
import { Box, MenuItem, Select, Typography } from "@mui/material";
import { VoiceToggle } from "../ui";

interface ChatPlaybackSettingsProps {
  voiceEnabled: boolean;
  isAudioPlaying: boolean;
  isAnyProcessing: boolean;
  speechSpeed: number;
  onVoiceEnabledChange: (value: boolean) => void;
  onSpeechSpeedChange: (value: number) => void;
}

const SPEED_OPTIONS = [
  0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25,
];

export const ChatPlaybackSettings: React.FC<ChatPlaybackSettingsProps> = ({
  voiceEnabled,
  isAudioPlaying,
  isAnyProcessing,
  speechSpeed,
  onVoiceEnabledChange,
  onSpeechSpeedChange,
}) => {
  return (
    <Box
      sx={{
        display: "flex",
        gap: { xs: 1.5, md: 2.5 },
        alignItems: "center",
        pl: 0.25,
        pt: 0.5,
      }}
    >
      <VoiceToggle
        enabled={voiceEnabled}
        onChange={onVoiceEnabledChange}
        isPlaying={isAudioPlaying}
        disabled={isAnyProcessing}
      />

      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Typography variant="caption" sx={{ color: "#9ca3af" }}>
          Speed:
        </Typography>
        <Select
          value={speechSpeed}
          onChange={(event) => onSpeechSpeedChange(Number(event.target.value))}
          size="small"
          variant="standard"
          sx={{
            color: "#9ca3af",
            fontSize: "0.8rem",
            "& .MuiSelect-select": { py: 0, pr: 3 },
            "&:before": { borderColor: "#4b5563" },
            "&:hover:not(.Mui-disabled):before": {
              borderColor: "#9ca3af",
            },
          }}
        >
          {SPEED_OPTIONS.map((speed) => (
            <MenuItem key={speed} value={speed}>
              {speed.toFixed(2)}x
            </MenuItem>
          ))}
        </Select>
      </Box>
    </Box>
  );
};
