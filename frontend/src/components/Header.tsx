import React from 'react';
import { Typography, Box } from '@mui/material';
import { Diamond, User, LogOut, MessageCircle } from 'lucide-react';
import { CustomButton } from './ui';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  currentView: 'analyzer' | 'vocabulary' | 'grammar' | 'chat' | 'profile';
  onViewChange: (view: 'analyzer' | 'vocabulary' | 'grammar' | 'chat' | 'profile') => void;
}

const Header: React.FC<HeaderProps> = ({ currentView, onViewChange }) => {
  const { logout } = useAuth();

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
        <CustomButton
          variant="secondary"
          onClick={() => onViewChange('analyzer')}
          sx={{
            color: currentView === 'analyzer' ? 'var(--primary-color)' : '#9ca3af',
            backgroundColor: currentView === 'analyzer' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
            '&:hover': {
              color: 'white',
              backgroundColor: currentView === 'analyzer' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
            },
          }}
        >
          Analyzer
        </CustomButton>
        <CustomButton
          variant="secondary"
          onClick={() => onViewChange('vocabulary')}
          sx={{
            color: currentView === 'vocabulary' ? 'var(--primary-color)' : '#9ca3af',
            backgroundColor: currentView === 'vocabulary' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
            '&:hover': {
              color: 'white',
              backgroundColor: currentView === 'vocabulary' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
            },
          }}
        >
          Vocabulary
        </CustomButton>
         <CustomButton
           variant="secondary"
           onClick={() => onViewChange('grammar')}
           sx={{
             color: currentView === 'grammar' ? 'var(--primary-color)' : '#9ca3af',
             backgroundColor: currentView === 'grammar' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
             '&:hover': {
               color: 'white',
               backgroundColor: currentView === 'grammar' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
             },
           }}
         >
           Grammar
         </CustomButton>
         <CustomButton
           variant="secondary"
           onClick={() => onViewChange('chat')}
           sx={{
             color: currentView === 'chat' ? 'var(--primary-color)' : '#9ca3af',
             backgroundColor: currentView === 'chat' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
             '&:hover': {
               color: 'white',
               backgroundColor: currentView === 'chat' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
             },
           }}
         >
           <MessageCircle size={16} style={{ marginRight: 4 }} />
           Chat
         </CustomButton>
         <CustomButton
           variant="secondary"
           onClick={() => onViewChange('profile')}
           sx={{
             color: currentView === 'profile' ? 'var(--primary-color)' : '#9ca3af',
             backgroundColor: currentView === 'profile' ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
             '&:hover': {
               color: 'white',
               backgroundColor: currentView === 'profile' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
             },
           }}
         >
           <User size={16} style={{ marginRight: 4 }} />
           Profile
         </CustomButton>
        <CustomButton
          variant="secondary"
          onClick={logout}
          sx={{
            color: '#ef4444',
            backgroundColor: 'transparent',
            '&:hover': {
              color: 'white',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
            },
          }}
        >
          <LogOut size={16} style={{ marginRight: 4 }} />
          Logout
        </CustomButton>
      </Box>
      </Box>
    </header>
  );
};

export default Header;
