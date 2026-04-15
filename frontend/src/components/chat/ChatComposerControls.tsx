import React from "react";
import { Box, Checkbox, FormControlLabel, MenuItem, Select, Typography } from "@mui/material";
import { ImageUploadButton, VoiceRecordButton } from "../ui";

interface ChatComposerControlsProps {
  isAnyProcessing: boolean;
  isRecording: boolean;
  canUseMicrophone: boolean;
  isTranscribing: boolean;
  recordedDuration: number;
  autoSend: boolean;
  improveTranscription: boolean;
  speechLanguage: string;
  languages: readonly string[];
  onImageUpload: (file: File) => void | Promise<void>;
  onImageError: (message: string) => void;
  onStartRecording: () => void | Promise<void>;
  onStopRecording: () => void | Promise<void>;
  onAutoSendChange: (value: boolean) => void;
  onImproveTranscriptionChange: (value: boolean) => void;
  onSpeechLanguageChange: (value: string) => void;
}

export const ChatComposerControls: React.FC<ChatComposerControlsProps> = ({
  isAnyProcessing,
  isRecording,
  canUseMicrophone,
  isTranscribing,
  recordedDuration,
  autoSend,
  improveTranscription,
  speechLanguage,
  languages,
  onImageUpload,
  onImageError,
  onStartRecording,
  onStopRecording,
  onAutoSendChange,
  onImproveTranscriptionChange,
  onSpeechLanguageChange,
}) => {
  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        gap: { xs: 1, md: 1.5 },
        alignItems: "center",
        justifyContent: "space-between",
        py: 0.5,
      }}
    >
      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <ImageUploadButton
          onFileSelect={onImageUpload}
          onError={onImageError}
          disabled={isAnyProcessing || isRecording}
        />
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <VoiceRecordButton
            isRecording={isRecording}
            isProcessing={isTranscribing}
            duration={recordedDuration}
            onStartRecording={onStartRecording}
            onStopRecording={onStopRecording}
            disabled={isAnyProcessing || !canUseMicrophone}
          />
          {!canUseMicrophone && (
            <Typography
              variant="caption"
              sx={{
                color: "#9ca3af",
                fontSize: "0.65rem",
                lineHeight: 1,
              }}
            >
              HTTPS required
            </Typography>
          )}
        </Box>
      </Box>

      <Box
        sx={{
          display: "flex",
          gap: { xs: 1, md: 1.5 },
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <FormControlLabel
          control={
            <Checkbox
              checked={autoSend}
              onChange={(event) => onAutoSendChange(event.target.checked)}
              size="small"
              sx={{
                color: "#9ca3af",
                p: 0.5,
                "&.Mui-checked": { color: "var(--primary-color)" },
              }}
            />
          }
          label="Autosend"
          sx={{
            color: "#9ca3af",
            m: 0,
            px: 1,
            py: 0.25,
            borderRadius: "8px",
            backgroundColor: "rgba(255, 255, 255, 0.04)",
            "& .MuiFormControlLabel-label": { fontSize: "0.75rem" },
          }}
        />

        <FormControlLabel
          control={
            <Checkbox
              checked={improveTranscription}
              onChange={(event) => onImproveTranscriptionChange(event.target.checked)}
              size="small"
              sx={{
                color: "#9ca3af",
                p: 0.5,
                "&.Mui-checked": {
                  color: "var(--primary-color)",
                },
              }}
            />
          }
          label="Improve transcription"
          sx={{
            color: "#9ca3af",
            m: 0,
            px: 1,
            py: 0.25,
            borderRadius: "8px",
            backgroundColor: "rgba(255, 255, 255, 0.04)",
            "& .MuiFormControlLabel-label": {
              fontSize: "0.75rem",
            },
          }}
        />

        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="caption" sx={{ color: "#9ca3af" }}>
            Speech:
          </Typography>
          <Select
            value={speechLanguage}
            onChange={(event) => onSpeechLanguageChange(event.target.value)}
            size="small"
            variant="standard"
            inputProps={{ "aria-label": "Speech language" }}
            sx={{
              color: "#9ca3af",
              fontSize: "0.8rem",
              minWidth: 100,
              "& .MuiSelect-select": { py: 0, pr: 3 },
              "&:before": { borderColor: "#4b5563" },
              "&:hover:not(.Mui-disabled):before": {
                borderColor: "#9ca3af",
              },
            }}
          >
            {languages.map((language) => (
              <MenuItem key={language} value={language}>
                {language}
              </MenuItem>
            ))}
          </Select>
        </Box>
      </Box>
    </Box>
  );
};
