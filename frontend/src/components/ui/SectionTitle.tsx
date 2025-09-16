import React from 'react';
import { Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

interface SectionTitleProps {
  children: React.ReactNode;
  variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  marginBottom?: number;
  color?: string;
  fontWeight?: string | number;
  sx?: SxProps<Theme>;
}

const SectionTitle: React.FC<SectionTitleProps> = ({
  children,
  variant = 'h4',
  marginBottom = 4,
  color = 'white',
  fontWeight = 'bold',
  sx = {},
}) => {
  return (
    <Typography
      variant={variant}
      sx={{
        mb: marginBottom,
        color,
        fontWeight,
        ...sx,
      }}
    >
      {children}
    </Typography>
  );
};

export default SectionTitle;