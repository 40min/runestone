import React, { useState } from 'react';
import { Typography, Box, IconButton, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';
import { Diamond, User, LogOut, MessageCircle, BookOpen, ScrollText, Menu, X, Repeat2 } from 'lucide-react';
import { CustomButton } from './ui';
import { useAuth } from '../context/AuthContext';
import type { ViewType } from '../types/navigation';

const headerFontFamily = '"Space Grotesk", "Noto Sans", sans-serif';
const headerBackground = 'linear-gradient(180deg, rgba(15, 24, 58, 0.98) 0%, rgba(6, 11, 38, 0.96) 100%)';
const headerBorder = '1px solid rgba(99, 114, 173, 0.35)';
const headerTextColor = '#f3f6ff';
const headerMutedTextColor = '#a8b6d8';
const activeNavBackground = 'rgba(56, 224, 123, 0.12)';
const activeNavHoverBackground = 'rgba(56, 224, 123, 0.18)';
const navHoverBackground = 'rgba(148, 163, 184, 0.08)';

interface HeaderProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
}

const Header: React.FC<HeaderProps> = ({ currentView, onViewChange }) => {
  const { logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const navItems: { id: ViewType; label: string; icon: React.ReactNode }[] = [
    { id: 'analyzer', label: 'Analyzer', icon: <Diamond size={20} /> },
    { id: 'vocabulary', label: 'Vocabulary', icon: <BookOpen size={20} /> },
    { id: 'recall', label: 'Recall', icon: <Repeat2 size={20} /> },
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
        background: headerBackground,
        color: headerTextColor,
        fontFamily: headerFontFamily,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box sx={{ py: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2, borderBottom: headerBorder }}>
        <Diamond size={24} style={{ color: 'var(--primary-color)' }} />
        <Typography variant="h6" sx={{ color: headerTextColor, fontFamily: headerFontFamily, fontWeight: 700, letterSpacing: '-0.02em' }}>
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
                backgroundColor: currentView === item.id ? activeNavBackground : 'transparent',
                color: currentView === item.id ? 'var(--primary-color)' : headerMutedTextColor,
                fontFamily: headerFontFamily,
                '&:hover': {
                  backgroundColor: currentView === item.id ? activeNavHoverBackground : navHoverBackground,
                  color: headerTextColor,
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
                  fontSize: '1rem',
                  fontFamily: headerFontFamily,
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Box sx={{ p: 2, borderTop: headerBorder }}>
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
          fontFamily: headerFontFamily,
          px: { xs: 2, md: 10 },
          py: { xs: 2, md: 3 },
          borderBottom: headerBorder,
          background: headerBackground,
          boxShadow: '0 10px 30px rgba(2, 6, 23, 0.18)',
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
              color: headerTextColor,
              fontFamily: headerFontFamily,
              fontSize: '1.25rem',
              fontWeight: 700,
              lineHeight: '1.625rem',
              letterSpacing: '-0.02em',
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
                color: currentView === item.id ? 'var(--primary-color)' : headerMutedTextColor,
                backgroundColor: currentView === item.id ? activeNavBackground : 'transparent',
                fontFamily: headerFontFamily,
                '&:hover': {
                  color: headerTextColor,
                  backgroundColor: currentView === item.id ? activeNavHoverBackground : navHoverBackground,
                },
              }}
            >
              {item.id === 'chat' || item.id === 'profile' ? (
                 <span style={{ display: 'flex', alignItems: 'center' }}>
                   {React.cloneElement(item.icon as React.ReactElement<{ size?: number; style?: React.CSSProperties }>, { size: 16, style: { marginRight: 4 } })}
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
              fontFamily: headerFontFamily,
              '&:hover': {
                color: headerTextColor,
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
          sx={{
            display: { md: 'none' },
            color: headerTextColor,
            '&:hover': { backgroundColor: navHoverBackground },
          }}
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
            background: headerBackground,
            borderLeft: headerBorder,
          },
        }}
      >
        {drawer}
      </Drawer>
    </header>
  );
};

export default Header;
