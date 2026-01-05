import React, { useState } from 'react';
import { Typography, Box, IconButton, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';
import { Diamond, User, LogOut, MessageCircle, BookOpen, ScrollText, Menu, X } from 'lucide-react';
import { CustomButton } from './ui';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  currentView: 'analyzer' | 'vocabulary' | 'grammar' | 'chat' | 'profile';
  onViewChange: (view: 'analyzer' | 'vocabulary' | 'grammar' | 'chat' | 'profile') => void;
}

const Header: React.FC<HeaderProps> = ({ currentView, onViewChange }) => {
  const { logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  type ViewType = 'analyzer' | 'vocabulary' | 'grammar' | 'chat' | 'profile';

  const navItems: { id: ViewType; label: string; icon: React.ReactNode }[] = [
    { id: 'analyzer', label: 'Analyzer', icon: <Diamond size={20} /> },
    { id: 'vocabulary', label: 'Vocabulary', icon: <BookOpen size={20} /> },
    { id: 'grammar', label: 'Grammar', icon: <ScrollText size={20} /> },
    { id: 'chat', label: 'Chat', icon: <MessageCircle size={20} /> },
    { id: 'profile', label: 'Profile', icon: <User size={20} /> },
  ];

  const drawer = (
    <Box
      onClick={handleDrawerToggle}
      sx={{
        textAlign: 'center',
        height: '100%',
        backgroundColor: '#1a102b',
        color: 'white',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box sx={{ py: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2, borderBottom: '1px solid #3a2d4a' }}>
        <Diamond size={24} style={{ color: 'var(--primary-color)' }} />
        <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
          Runestone
        </Typography>
      </Box>
      <List sx={{ flexGrow: 1, px: 2, py: 3 }}>
        {navItems.map((item) => (
          <ListItem key={item.id} disablePadding sx={{ mb: 1 }}>
            <ListItemButton
              onClick={() => onViewChange(item.id)}
              sx={{
                textAlign: 'left',
                borderRadius: '0.5rem',
                backgroundColor: currentView === item.id ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
                color: currentView === item.id ? 'var(--primary-color)' : '#9ca3af',
                '&:hover': {
                  backgroundColor: currentView === item.id ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
                  color: 'white',
                },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit', minWidth: 40 }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{
                  fontWeight: currentView === item.id ? 'bold' : 'medium',
                  fontSize: '1rem'
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Box sx={{ p: 2, borderTop: '1px solid #3a2d4a' }}>
        <CustomButton
          variant="secondary"
          onClick={logout}
          fullWidth
          sx={{
            color: '#ef4444',
            justifyContent: 'flex-start',
            '&:hover': { backgroundColor: 'rgba(239, 68, 68, 0.1)' },
          }}
        >
          <LogOut size={20} style={{ marginRight: 12 }} />
          Logout
        </CustomButton>
      </Box>
    </Box>
  );

  return (
    <header>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: { xs: 2, md: 10 },
          py: { xs: 2, md: 3 },
          borderBottom: '1px solid #3a2d4a',
          backgroundColor: '#1a102b',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 2, md: 4 } }}>
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

        {/* Desktop Navigation */}
        <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 2, alignItems: 'center' }}>
          {navItems.map((item) => (
            <CustomButton
              key={item.id}
              variant="secondary"
              onClick={() => onViewChange(item.id)}
              sx={{
                color: currentView === item.id ? 'var(--primary-color)' : '#9ca3af',
                backgroundColor: currentView === item.id ? 'rgba(147, 51, 234, 0.1)' : 'transparent',
                '&:hover': {
                  color: 'white',
                  backgroundColor: currentView === item.id ? 'rgba(147, 51, 234, 0.2)' : 'rgba(156, 163, 175, 0.1)',
                },
              }}
            >
              {item.id === 'chat' || item.id === 'profile' ? (
                 <span style={{ display: 'flex', alignItems: 'center' }}>
                   {React.cloneElement(item.icon as React.ReactElement, { size: 16, style: { marginRight: 4 } })}
                   {item.label}
                 </span>
              ) : (
                item.label
              )}
            </CustomButton>
          ))}
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

        {/* Mobile Menu Button */}
        <IconButton
          color="inherit"
          aria-label="open drawer"
          edge="start"
          onClick={handleDrawerToggle}
          sx={{ display: { md: 'none' }, color: 'white' }}
        >
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </IconButton>
      </Box>

      {/* Mobile Drawer */}
      <Drawer
        variant="temporary"
        anchor="right"
        open={mobileOpen}
        onClose={handleDrawerToggle}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile.
        }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: 280,
            backgroundColor: '#1a102b',
            borderLeft: '1px solid #3a2d4a'
          },
        }}
      >
        {drawer}
      </Drawer>
    </header>
  );
};

export default Header;
