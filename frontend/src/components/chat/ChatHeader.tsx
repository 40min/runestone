import { Box, IconButton, Tooltip, Typography } from "@mui/material";
import PsychologyIcon from "@mui/icons-material/Psychology";
import { MessageCircle } from "lucide-react";
import { NewChatButton } from "../ui";
import { TeacherAvatar } from "./TeacherAvatar";
import type { TeacherEmotion } from "../../types/teacherEmotion";

interface ChatHeaderProps {
  onNewChat: () => void;
  onOpenMemory: () => void;
  isLoading: boolean;
  hasMessages: boolean;
  isBackendAvailable?: boolean;
  teacherEmotion?: TeacherEmotion | string | null;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  onNewChat,
  onOpenMemory,
  isLoading,
  hasMessages,
  isBackendAvailable = true,
  teacherEmotion,
}) => {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        px: { xs: 2, md: 5 },
        py: { xs: 1.5, md: 2 },
        borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
        gap: 2,
        minHeight: { xs: 92, md: 102 },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <TeacherAvatar
          size={73}
          showStatus
          isBackendAvailable={isBackendAvailable}
          emotion={isLoading ? "thinking" : teacherEmotion}
        />
        <Box>
          <Typography
            variant="h5"
            sx={{
              color: "white",
              fontWeight: 700,
              mb: 0.25,
              fontSize: { xs: "1.25rem", md: "1.45rem" },
              lineHeight: 1.1,
            }}
          >
            Björn
          </Typography>
          <Typography
            sx={{
              color: "#9ca3af",
              fontSize: { xs: "0.82rem", md: "0.95rem" },
            }}
          >
            Your Swedish Teacher
          </Typography>
        </Box>
      </Box>

      <Box
        sx={{
          display: "flex",
          gap: { xs: 0.5, md: 1.25 },
          alignItems: "center",
        }}
      >
        <Tooltip title="Teacher's Memory">
          <IconButton
            aria-label="Open teacher memory"
            onClick={onOpenMemory}
            sx={{
              width: 38,
              height: 38,
              color: "var(--primary-color)",
              bgcolor: "rgba(56, 224, 123, 0.08)",
              border: "1px solid rgba(56, 224, 123, 0.12)",
              "&:hover": { bgcolor: "rgba(56, 224, 123, 0.16)" },
            }}
          >
            <PsychologyIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title="Starts a new chat session. Previous chats are archived.">
          <Box component="span" sx={{ display: { xs: "none", md: "block" } }}>
            <NewChatButton
              onClick={onNewChat}
              isLoading={isLoading}
              hasMessages={hasMessages}
            />
          </Box>
        </Tooltip>

        <Tooltip title="Starts a new chat session. Previous chats are archived.">
          <Box component="span" sx={{ display: { xs: "inline-flex", md: "none" } }}>
            <IconButton
              aria-label="New chat"
              onClick={onNewChat}
              disabled={isLoading || !hasMessages}
              sx={{
                width: 38,
                height: 38,
                color: "var(--primary-color)",
                "&:hover": { bgcolor: "rgba(56, 224, 123, 0.12)" },
              }}
            >
              <MessageCircle size={18} />
            </IconButton>
          </Box>
        </Tooltip>
      </Box>
    </Box>
  );
};
