import React from 'react';
import { Box } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

interface ContentCardProps {
  children: React.ReactNode;
  padding?: number | string;
  backgroundColor?: string;
  borderRadius?: string;
  sx?: SxProps<Theme>;
}

const ContentCard: React.FC<ContentCardProps> = ({
  children,
  padding = { xs: 2, md: 4 },
  backgroundColor = '#2a1f35',
  borderRadius = '0.5rem',
  sx = {},
}) => {
  return (
    <Box
      sx={{
        p: padding,
        backgroundColor,
        borderRadius,
        ...sx,
      }}
    >
      {children}
    </Box>
  );
};

export default ContentCard;
