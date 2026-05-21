import React from "react";
import type { SxProps, Theme } from "@mui/material";
import ContentCard from "./ContentCard";
import {
  analyzerSurfaceBackground,
  analyzerSurfaceCardSx,
  analyzerSurfaceRadius,
} from "./analyzerStyles";

interface SurfaceCardProps {
  children: React.ReactNode;
  padding?: number | string;
  sx?: SxProps<Theme>;
}

const SurfaceCard: React.FC<SurfaceCardProps> = ({
  children,
  padding = { xs: 2, md: 4 },
  sx = {},
}) => {
  const mergedSx: SxProps<Theme> = [
    analyzerSurfaceCardSx,
    ...(Array.isArray(sx) ? sx : [sx]),
  ];

  return (
    <ContentCard
      padding={padding}
      backgroundColor={analyzerSurfaceBackground}
      borderRadius={analyzerSurfaceRadius}
      sx={mergedSx}
    >
      {children}
    </ContentCard>
  );
};

export default SurfaceCard;
