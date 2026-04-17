import React, { useState } from "react";
import { Box, Button, IconButton, Link, Typography } from "@mui/material";
import {
  ChevronDown,
  ChevronUp,
  Pause,
  Play,
  RotateCcw,
} from "lucide-react";
import { TeacherAvatar } from "../chat/TeacherAvatar";
import { AssistantMessageContent } from "./AssistantMessageContent";
import { formatResponseTime } from "./ChatMessageBubble.utils";
import type { TeacherEmotion } from "../../types/teacherEmotion";

interface ChatMessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  sources?: { title: string; url: string; date: string }[] | null;
  teacherEmotion?: TeacherEmotion | string | null;
  responseTimeMs?: number;
  createdAt?: string;
  isLast?: boolean;
  isLatestByRole?: boolean;
  showAudioControls?: boolean;
  isAudioPlaying?: boolean;
  canReplayAudio?: boolean;
  onPlayAudio?: () => void;
  onPauseAudio?: () => void;
  onReplayAudio?: () => void;
}

const formatMessageTime = (value?: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
};

export const ChatMessageBubble: React.FC<ChatMessageBubbleProps> = ({
  role,
  content,
  sources,
  teacherEmotion,
  responseTimeMs,
  createdAt,
  isLast,
  isLatestByRole = false,
  showAudioControls = false,
  isAudioPlaying = false,
  canReplayAudio = false,
  onPlayAudio,
  onPauseAudio,
  onReplayAudio,
}) => {
  const maxCollapsedChars = 300;
  const isLongMessage = content.length > maxCollapsedChars;
  const [isExpanded, setIsExpanded] = useState(false);
  const shouldKeepExpanded = isLast || isLatestByRole;
  const isCollapsed = !shouldKeepExpanded && isLongMessage && !isExpanded;
  const hasSources = role === "assistant" && sources && sources.length > 0;
  const messageTime = formatMessageTime(createdAt);
  const showResponseTime =
    role === "assistant" &&
    typeof responseTimeMs === "number" &&
    Number.isFinite(responseTimeMs) &&
    responseTimeMs >= 0;
  const responseTimeLabel = showResponseTime
    ? `Teacher responded in ${formatResponseTime(responseTimeMs)}`
    : null;
  const resolveSafeUrl = (url: string) => {
    try {
      const parsed = new URL(url);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") {
        return parsed.toString();
      }
    } catch {
      return null;
    }
    return null;
  };
  const renderContentWithLinks = (text: string): React.ReactNode => {
    if (!text) return text;

    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    const nodes: React.ReactNode[] = [];

    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      const isUrl = index % 2 === 1;
      if (!isUrl) {
        nodes.push(part);
        continue;
      }

      let url = part;
      let trailing = "";
      while (url.length > 0 && /[).,;:!?]/.test(url[url.length - 1])) {
        trailing = url[url.length - 1] + trailing;
        url = url.slice(0, -1);
      }

      const safeUrl = resolveSafeUrl(url);
      if (safeUrl) {
        nodes.push(
          <Link
            key={`link-${index}`}
            href={safeUrl}
            target="_blank"
            rel="noopener noreferrer"
            underline="always"
            sx={{
              color: "var(--primary-color)",
              textDecorationColor: "var(--primary-color)",
              fontWeight: 500,
              "&:hover": {
                color: "var(--primary-color)",
              },
            }}
          >
            {url}
          </Link>,
        );
      } else {
        nodes.push(part);
      }

      if (trailing) nodes.push(trailing);
    }

    return nodes;
  };
  const formatDate = (value: string) => {
    if (!value) return value;
    return value.replace(/\.\d+(?=Z|$)/, "");
  };
  const displayedContent = isCollapsed
    ? content.slice(0, maxCollapsedChars)
    : content;

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: role === "user" ? "flex-end" : "flex-start",
        alignItems: "flex-end",
        gap: 1.25,
        mb: { xs: 1.75, md: 2 },
      }}
    >
      {role === "assistant" && (
        <TeacherAvatar size={44} showStatus={false} emotion={teacherEmotion} />
      )}
      <Box
        sx={{
          maxWidth:
            role === "user"
              ? { xs: "86%", sm: "62%", md: "65%" }
              : { xs: "calc(100% - 56px)", sm: "78%", md: "70%" },
          padding: role === "user" ? "10px 15px" : "12px 18px",
          borderRadius:
            role === "user" ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
          backgroundColor:
            role === "user"
              ? "rgba(58, 30, 104, 0.92)"
              : "rgba(43, 31, 65, 0.88)",
          border:
            role === "user"
              ? "1px solid rgba(147, 51, 234, 0.32)"
              : "1px solid rgba(255, 255, 255, 0.04)",
          boxShadow:
            role === "assistant"
              ? "0 18px 44px rgba(0, 0, 0, 0.12)"
              : "none",
        }}
      >
        {role === "assistant" ? (
          <Box
            sx={{
              color: "#f4efff",
              "& .markdown-content": {
                lineHeight: 1.65,
              },
              "& .markdown-content p:first-of-type": {
                marginTop: 0,
              },
              "& .markdown-content p:last-child": {
                marginBottom: 0,
              },
            }}
          >
            <AssistantMessageContent content={displayedContent} />
            {isCollapsed && (
              <Box
                component="span"
                sx={{
                  color: "var(--primary-color)",
                  fontWeight: 800,
                  letterSpacing: "0.12em",
                  ml: 0.5,
                }}
              >
                ...
              </Box>
            )}
          </Box>
        ) : (
          <Typography
            component="div"
            sx={{
              color: "white",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              lineHeight: 1.55,
            }}
          >
            {renderContentWithLinks(displayedContent)}
            {isCollapsed && (
              <Box
                component="span"
                sx={{
                  color: "var(--primary-color)",
                  fontWeight: 800,
                  letterSpacing: "0.12em",
                  ml: 0.5,
                }}
              >
                ...
              </Box>
            )}
          </Typography>
        )}

        {!shouldKeepExpanded && isLongMessage && (
          <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
            <IconButton
              onClick={() => setIsExpanded(!isExpanded)}
              size="small"
              aria-label={isExpanded ? "Show less" : "Show more"}
              sx={{
                color: "var(--primary-color)",
                mt: 0.5,
                backgroundColor: "rgba(56, 224, 123, 0.08)",
                borderRadius: "6px",
                "&:hover": {
                  backgroundColor: "rgba(56, 224, 123, 0.14)",
                },
              }}
            >
              {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </IconButton>
          </Box>
        )}
        {role === "assistant" && showAudioControls && (
          <Box
            sx={{
              display: "flex",
              gap: 1,
              flexWrap: "wrap",
              mt: 1.25,
              pt: 1,
              borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {isAudioPlaying ? (
              <Button
                size="small"
                variant="text"
                onClick={onPauseAudio}
                startIcon={<Pause size={14} />}
                sx={{
                  color: "var(--primary-color)",
                  minWidth: "auto",
                  px: 1,
                }}
              >
                Pause
              </Button>
            ) : (
              <Button
                size="small"
                variant="text"
                onClick={onPlayAudio}
                disabled={!canReplayAudio}
                startIcon={<Play size={14} />}
                sx={{
                  color: "var(--primary-color)",
                  minWidth: "auto",
                  px: 1,
                }}
              >
                Play
              </Button>
            )}
            <Button
              size="small"
              variant="text"
              onClick={onReplayAudio}
              disabled={!canReplayAudio}
              startIcon={<RotateCcw size={14} />}
              sx={{
                color: "var(--primary-color)",
                minWidth: "auto",
                px: 1,
              }}
            >
              Replay
            </Button>
          </Box>
        )}
        {hasSources && (
          <Box sx={{ mt: 1.5 }}>
            <Typography
              sx={(theme) => ({
                color: theme.palette.primary.light,
                fontSize: "0.75rem",
                mb: 0.5,
              })}
            >
              Sources
            </Typography>
            <Box
              component="ul"
              sx={{
                listStyle: "none",
                p: 0,
                m: 0,
                display: "grid",
                gap: 0.75,
              }}
            >
              {sources.map((source) => (
                <Box component="li" key={source.url}>
                  {(() => {
                    const safeUrl = resolveSafeUrl(source.url);
                    return safeUrl ? (
                      <Link
                        href={safeUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        underline="always"
                        sx={{
                          color: "var(--primary-color)",
                          textDecorationColor: "var(--primary-color)",
                          fontSize: "0.9rem",
                          fontWeight: 500,
                          "&:hover": {
                            color: "var(--primary-color)",
                          },
                        }}
                      >
                        {source.title}
                      </Link>
                    ) : (
                      <Typography
                        sx={(theme) => ({
                          color: theme.palette.common.white,
                          fontSize: "0.9rem",
                          fontWeight: 500,
                        })}
                      >
                        {source.title}
                      </Typography>
                    );
                  })()}
                  {source.date && (
                    <Typography
                      sx={(theme) => ({
                        color: theme.palette.grey[300],
                        fontSize: "0.75rem",
                        mt: 0.25,
                      })}
                    >
                      {formatDate(source.date)}
                    </Typography>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        )}
        {(responseTimeLabel || messageTime) && (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              mt: 1,
            }}
          >
            {responseTimeLabel && (
              <Typography
                sx={{
                  color: "rgba(255, 255, 255, 0.42)",
                  fontSize: "0.72rem",
                  lineHeight: 1,
                }}
              >
                {responseTimeLabel}
              </Typography>
            )}
            {messageTime && (
              <Typography
                sx={{
                  color: "rgba(255, 255, 255, 0.42)",
                  fontSize: "0.72rem",
                  lineHeight: 1,
                  ml: "auto",
                }}
              >
                {messageTime}
              </Typography>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
};
