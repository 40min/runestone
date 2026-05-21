import React from "react";
import type { SxProps, Theme } from "@mui/material";
import ContentCard from "./ContentCard";

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
  return (
    <ContentCard
      padding={padding}
      backgroundColor="rgba(40, 29, 56, 0.92)"
      borderRadius="0.9rem"
      sx={{
        border: "1px solid rgba(95, 76, 123, 0.82)",
        ...sx,
      }}
    >
      {children}
    </ContentCard>
  );
};

export default SurfaceCard;
