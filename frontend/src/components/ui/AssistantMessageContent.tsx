import React from "react";
import { Box } from "@mui/material";
import { Lightbulb } from "lucide-react";
import MarkdownDisplay from "./MarkdownDisplay";

interface AssistantMessageContentProps {
  content: string;
}

const isTeachingCallout = (block: string) => {
  const trimmed = block.trim();
  return (
    trimmed.startsWith("💡") ||
    /^(\*\*)?["“][^"”\n]+["”](\*\*)?[.:]?/.test(trimmed)
  );
};

const stripCalloutMarker = (block: string) => block.trim().replace(/^💡\s*/, "");

export const AssistantMessageContent: React.FC<AssistantMessageContentProps> = ({
  content,
}) => {
  const blocks = content.split(/\n{2,}/);

  return (
    <>
      {blocks.map((block, index) => {
        const trimmed = block.trim();
        if (!trimmed) {
          return null;
        }

        if (isTeachingCallout(trimmed)) {
          return (
            <Box
              key={`callout-${index}`}
              data-testid="teaching-callout"
              sx={{
                display: "flex",
                alignItems: "flex-start",
                gap: 1,
                my: 1.25,
                px: 1.5,
                py: 1,
                borderRadius: "8px",
                backgroundColor: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.04)",
              }}
            >
              <Lightbulb
                size={16}
                style={{
                  flexShrink: 0,
                  marginTop: 4,
                  color: "#facc15",
                }}
              />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <MarkdownDisplay markdownContent={stripCalloutMarker(trimmed)} />
              </Box>
            </Box>
          );
        }

        return <MarkdownDisplay key={`content-${index}`} markdownContent={trimmed} />;
      })}
    </>
  );
};
