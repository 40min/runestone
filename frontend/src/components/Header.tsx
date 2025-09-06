import React from 'react';
import { Typography, Box } from '@mui/material';
import { Diamond } from 'lucide-react';

const Header: React.FC = () => {
  return (
    <header>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 10,
          py: 3,
          borderBottom: '1px solid #3a2d4a',
          backgroundColor: '#1a102b',
        }}
      >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Diamond size={24} style={{ color: 'var(--primary-color)' }} />
        <Typography
          variant="h6"
          component="h1"
          sx={{
            color: 'white',
            fontSize: '1.25rem',
            fontWeight: 'bold',
            lineHeight: '1.625rem',
            tracking: '-0.015em',
          }}
        >
          Runestone
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        {/* Additional header content can go here */}
      </Box>
      </Box>
    </header>
  );
};

export default Header;