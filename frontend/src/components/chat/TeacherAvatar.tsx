import React, { useEffect, useRef, useState } from "react";
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

const avatarChromeByEmotion: Record<
  TeacherEmotion,
  { background: string; border: string; shadow: string }
> = {
  neutral: {
    background: "rgba(205, 186, 163, 0.94)",
    border: "rgba(145, 101, 69, 0.24)",
    shadow: "0 8px 20px rgba(24, 16, 10, 0.16)",
  },
  happy: {
    background: "rgba(211, 188, 158, 0.94)",
    border: "rgba(157, 95, 54, 0.24)",
    shadow: "0 8px 20px rgba(32, 18, 8, 0.15)",
  },
  sad: {
    background: "rgba(195, 186, 176, 0.94)",
    border: "rgba(118, 104, 92, 0.22)",
    shadow: "0 8px 20px rgba(20, 18, 16, 0.14)",
  },
  worried: {
    background: "rgba(196, 184, 172, 0.94)",
    border: "rgba(119, 102, 90, 0.22)",
    shadow: "0 8px 20px rgba(20, 18, 16, 0.14)",
  },
  concerned: {
    background: "rgba(203, 184, 163, 0.94)",
    border: "rgba(139, 96, 68, 0.23)",
    shadow: "0 8px 20px rgba(25, 17, 10, 0.15)",
  },
  thinking: {
    background: "rgba(199, 186, 170, 0.94)",
    border: "rgba(126, 105, 86, 0.22)",
    shadow: "0 8px 20px rgba(22, 18, 14, 0.14)",
  },
  hopeful: {
    background: "rgba(207, 190, 160, 0.94)",
    border: "rgba(151, 116, 61, 0.23)",
    shadow: "0 8px 20px rgba(26, 20, 10, 0.14)",
  },
  surprised: {
    background: "rgba(210, 187, 158, 0.94)",
    border: "rgba(154, 96, 56, 0.24)",
    shadow: "0 8px 20px rgba(31, 18, 8, 0.15)",
  },
  serious: {
    background: "rgba(195, 181, 166, 0.94)",
    border: "rgba(116, 96, 82, 0.22)",
    shadow: "0 8px 20px rgba(20, 16, 12, 0.14)",
  },
};

export const TeacherAvatar: React.FC<TeacherAvatarProps> = ({
  size = 48,
  src,
  emotion,
  alt = "Björn, your Swedish teacher",
  showStatus = false,
}) => {
  const CROSSFADE_MS = 220;
  const normalizedEmotion = normalizeTeacherEmotion(emotion);
  const avatarSrc = src ?? emotionAvatars[normalizedEmotion];
  const avatarChrome = avatarChromeByEmotion[normalizedEmotion];
  const [activeSrc, setActiveSrc] = useState<string | null>(avatarSrc ?? null);
  const [previousSrc, setPreviousSrc] = useState<string | null>(null);
  const [isCrossfading, setIsCrossfading] = useState(false);
  const clearPreviousTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (clearPreviousTimerRef.current !== null) {
      window.clearTimeout(clearPreviousTimerRef.current);
      clearPreviousTimerRef.current = null;
    }

    if (!avatarSrc) {
      setActiveSrc(null);
      setPreviousSrc(null);
      setIsCrossfading(false);
      return;
    }

    if (!activeSrc) {
      setActiveSrc(avatarSrc);
      return;
    }

    if (avatarSrc === activeSrc) {
      return;
    }

    setPreviousSrc(activeSrc);
    setActiveSrc(avatarSrc);
    setIsCrossfading(true);
    clearPreviousTimerRef.current = window.setTimeout(() => {
      setPreviousSrc(null);
      setIsCrossfading(false);
      clearPreviousTimerRef.current = null;
    }, CROSSFADE_MS);

    return () => {
      if (clearPreviousTimerRef.current !== null) {
        window.clearTimeout(clearPreviousTimerRef.current);
        clearPreviousTimerRef.current = null;
      }
    };
  }, [avatarSrc, activeSrc]);

  const avatarStyles = {
    width: "100%",
    height: "100%",
    borderRadius: "50%",
    clipPath: "circle(50% at 50% 50%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    background: avatarChrome.background,
    border: `1px solid ${avatarChrome.border}`,
    boxShadow: avatarChrome.shadow,
    color: "#101713",
    fontSize: Math.max(14, Math.floor(size * 0.42)),
    fontWeight: 800,
    objectFit: "cover",
    objectPosition: "center",
    userSelect: "none",
  };
  const avatarLayerStyles = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: "cover",
    objectPosition: "center",
    userSelect: "none",
    pointerEvents: "none",
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
      {activeSrc ? (
        <Box
          sx={{
            ...avatarStyles,
            position: "relative",
            "@keyframes teacher-avatar-fade-in": {
              from: { opacity: 0 },
              to: { opacity: 1 },
            },
            "@keyframes teacher-avatar-fade-out": {
              from: { opacity: 1 },
              to: { opacity: 0 },
            },
          }}
        >
          {previousSrc && (
            <Box
              component="img"
              src={previousSrc}
              alt=""
              aria-hidden="true"
              sx={{
                ...avatarLayerStyles,
                animation: `teacher-avatar-fade-out ${CROSSFADE_MS}ms ease-out forwards`,
              }}
            />
          )}
          <Box
            component="img"
            src={activeSrc}
            alt={alt}
            sx={{
              ...avatarLayerStyles,
              animation: isCrossfading
                ? `teacher-avatar-fade-in ${CROSSFADE_MS}ms ease-out forwards`
                : "none",
            }}
          />
        </Box>
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
