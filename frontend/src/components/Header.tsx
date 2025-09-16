import React from 'react';
import { Typography, Box, Button } from '@mui/material';
import { Diamond } from 'lucide-react';

interface HeaderProps {
  currentView: 'analyzer' | 'vocabulary';
  onViewChange: (view: 'analyzer' | 'vocabulary') => void;
}

const Header: React.FC<HeaderProps> = ({ currentView, onViewChange }) => {
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
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        <Button
          onClick={() => onViewChange('analyzer')}
          sx={{
            color: currentView === 'analyzer' ? 'var(--primary-color)' : '#9ca3af',
            fontWeight: 'medium',
            fontSize: '0.875rem',
            textTransform: 'none',
            px: 2,
            py: 1,
            borderRadius: '0.5rem',
            backgroundColor: currentView === 'analyzer' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
            '&:hover': {
              color: 'white',
              backgroundColor: currentView === 'analyzer' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
            },
            transition: 'all 0.2s',
          }}
        >
          Analyzer
        </Button>
        <Button
          onClick={() => onViewChange('vocabulary')}
          sx={{
            color: currentView === 'vocabulary' ? 'var(--primary-color)' : '#9ca3af',
            fontWeight: 'medium',
            fontSize: '0.875rem',
            textTransform: 'none',
            px: 2,
            py: 1,
            borderRadius: '0.5rem',
            backgroundColor: currentView === 'vocabulary' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
            '&:hover': {
              color: 'white',
              backgroundColor: currentView === 'vocabulary' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
            },
            transition: 'all 0.2s',
          }}
        >
          Vocabulary
        </Button>
      </Box>
      </Box>
    </header>
  );
};

export default Header;