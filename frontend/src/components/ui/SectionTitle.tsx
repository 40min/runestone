import React from 'react';
import { Typography, Box } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

interface SectionTitleProps {
  children: React.ReactNode;
  variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  marginBottom?: number;
  color?: string;
  fontWeight?: string | number;
  sx?: SxProps<Theme>;
  rightElement?: React.ReactNode; // New prop for element on the right
}

const SectionTitle: React.FC<SectionTitleProps> = ({
  children,
  variant = 'h4',
  marginBottom = 4,
  color = 'white',
  fontWeight = 'bold',
  sx = {},
  rightElement, // Destructure new prop
}) => {
  return (
    <Typography
      variant={variant}
      sx={{
        mb: marginBottom,
        color,
        fontWeight,
        display: "flex", // Added display flex
        alignItems: "center", // Added align items center
        gap: 1, // Added gap for spacing between children and rightElement
        ...sx,
      }}
    >
      {children}
      {rightElement && <Box sx={{ ml: 1 }}>{rightElement}</Box>} {/* Render rightElement */}
    </Typography>
  );
};

export default SectionTitle;
