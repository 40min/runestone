import React from "react";
import { Box } from "@mui/material";

interface TeacherAvatarProps {
  size?: number;
  src?: string;
  alt?: string;
  showStatus?: boolean;
}

export const TeacherAvatar: React.FC<TeacherAvatarProps> = ({
  size = 48,
  src,
  alt = "Björn, your Swedish teacher",
  showStatus = false,
}) => {
  return (
    <Box
      sx={{
        position: "relative",
        width: size,
        height: size,
        flex: `0 0 ${size}px`,
      }}
    >
      <Box
        component={src ? "img" : "div"}
        src={src}
        alt={src ? alt : undefined}
        aria-label={!src ? alt : undefined}
        role={!src ? "img" : undefined}
        sx={{
          width: "100%",
          height: "100%",
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "linear-gradient(135deg, rgba(56, 224, 123, 0.95), rgba(21, 128, 116, 0.95))",
          border: "1px solid rgba(255, 255, 255, 0.18)",
          boxShadow: "0 10px 28px rgba(0, 0, 0, 0.24)",
          color: "#101713",
          fontSize: Math.max(14, Math.floor(size * 0.42)),
          fontWeight: 800,
          objectFit: "cover",
          userSelect: "none",
        }}
      >
        {!src && "B"}
      </Box>
      {showStatus && (
        <Box
          aria-hidden="true"
          sx={{
            position: "absolute",
            right: 1,
            bottom: 1,
            width: Math.max(9, Math.floor(size * 0.22)),
            height: Math.max(9, Math.floor(size * 0.22)),
            borderRadius: "50%",
            backgroundColor: "var(--primary-color)",
            border: "2px solid #1a102b",
          }}
        />
      )}
    </Box>
  );
};
