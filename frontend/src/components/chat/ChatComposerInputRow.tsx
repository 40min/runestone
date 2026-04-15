import React from "react";
import { Box } from "@mui/material";
import { Send } from "lucide-react";
import { ChatInput, CustomButton } from "../ui";

interface ChatComposerInputRowProps {
  inputMessage: string;
  isAnyProcessing: boolean;
  isRecording: boolean;
  onInputChange: (value: string) => void;
  onKeyPress: (event: React.KeyboardEvent) => void;
  onSendMessage: () => void;
}

export const ChatComposerInputRow: React.FC<ChatComposerInputRowProps> = ({
  inputMessage,
  isAnyProcessing,
  isRecording,
  onInputChange,
  onKeyPress,
  onSendMessage,
}) => {
  return (
    <Box
      sx={{
        display: "flex",
        gap: { xs: 1, md: 1.5 },
        alignItems: "center",
      }}
    >
      <ChatInput
        value={inputMessage}
        onChange={(event) => onInputChange(event.target.value)}
        onKeyPress={onKeyPress}
        placeholder="Skriv ditt svar här..."
        disabled={isAnyProcessing || isRecording}
      />
      <CustomButton
        onClick={onSendMessage}
        disabled={!inputMessage.trim() || isAnyProcessing || isRecording}
        aria-label="Send message"
        sx={{
          minWidth: { xs: "48px", sm: "96px" },
          height: "46px",
          borderRadius: "8px",
          px: { xs: 0, sm: 3 },
          fontWeight: 700,
          letterSpacing: 0,
          "&.Mui-disabled": {
            backgroundColor: "rgba(56, 224, 123, 0.34)",
            color: "rgba(17, 23, 20, 0.7)",
            opacity: 1,
          },
        }}
      >
        <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
          SKICKA
        </Box>
        <Box component="span" sx={{ display: { xs: "inline-flex", sm: "none" } }}>
          <Send size={18} />
        </Box>
      </CustomButton>
    </Box>
  );
};
