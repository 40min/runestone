import React from "react";
import { Box } from "@mui/material";
import bjornConcerned from "../../assets/emotions/bjorn_concerned.png";
import bjornHappy from "../../assets/emotions/bjorn_happy.png";
import bjornHopeful from "../../assets/emotions/bjorn_hopeful.png";
import bjornNeutral from "../../assets/emotions/bjorn_neutral.png";
import bjornSad from "../../assets/emotions/bjorn_sad.png";
import bjornSerious from "../../assets/emotions/bjorn_serious.png";
import bjornSurprised from "../../assets/emotions/bjorn_surprised.png";
import bjornThinking from "../../assets/emotions/bjorn_thinking.png";
import bjornWorried from "../../assets/emotions/bjorn_worried.png";
import {
  normalizeTeacherEmotion,
  type TeacherEmotion,
} from "../../types/teacherEmotion";

interface TeacherAvatarProps {
  size?: number;
  src?: string;
  emotion?: TeacherEmotion | string | null;
  alt?: string;
  showStatus?: boolean;
}

const emotionAvatars: Record<TeacherEmotion, string> = {
  neutral: bjornNeutral,
  happy: bjornHappy,
  sad: bjornSad,
  worried: bjornWorried,
  concerned: bjornConcerned,
  thinking: bjornThinking,
  hopeful: bjornHopeful,
  surprised: bjornSurprised,
  serious: bjornSerious,
};

export const TeacherAvatar: React.FC<TeacherAvatarProps> = ({
  size = 48,
  src,
  emotion,
  alt = "Björn, your Swedish teacher",
  showStatus = false,
}) => {
  const avatarSrc = src ?? emotionAvatars[normalizeTeacherEmotion(emotion)];
  const avatarStyles = {
    width: "100%",
    height: "100%",
    borderRadius: "50%",
    clipPath: "circle(50% at 50% 50%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    background: "rgba(43, 31, 65, 0.88)",
    border: "1px solid rgba(255, 255, 255, 0.04)",
    boxShadow: "0 10px 28px rgba(0, 0, 0, 0.24)",
    color: "#101713",
    fontSize: Math.max(14, Math.floor(size * 0.42)),
    fontWeight: 800,
    objectFit: "cover",
    objectPosition: "center",
    userSelect: "none",
  };

  return (
    <Box
      sx={{
        position: "relative",
        width: size,
        height: size,
        flex: `0 0 ${size}px`,
      }}
    >
      {avatarSrc ? (
        <Box component="img" src={avatarSrc} alt={alt} sx={avatarStyles} />
      ) : (
        <Box aria-label={alt} role="img" sx={avatarStyles}>
          B
        </Box>
      )}
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
