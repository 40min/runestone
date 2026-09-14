import { useCallback, useState } from 'react';
import { Box, Typography, Button } from '@mui/material';
import { Refresh } from '@mui/icons-material';
import { useRegisterSW } from 'virtual:pwa-register/react';

/**
 * Registers the generated service worker and offers a user-controlled update
 * prompt. Runestone holds in-progress user input (forms, uploads, recordings,
 * chat drafts), so a new version never reloads the page automatically; the
 * user chooses when to activate it.
 */
const PwaUpdatePrompt = () => {
  const [dismissed, setDismissed] = useState(false);

  const { needRefresh, updateServiceWorker } = useRegisterSW({
    onRegisterError(error) {
      // Registration must stay non-fatal; the web app works without the worker.
      console.error('Service worker registration failed:', error);
    },
  });

  const handleReload = useCallback(() => {
    // Activating the waiting worker requires a page reload; the user has
    // explicitly accepted losing in-progress state by choosing Reload.
    updateServiceWorker(true);
  }, [updateServiceWorker]);

  if (!needRefresh[0] || dismissed) return null;

  return (
    <Box
      role="alertdialog"
      aria-label="Application update available"
      sx={{
        position: 'fixed',
        bottom: { xs: 16, sm: 24 },
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 2100,
        backgroundColor: '#1e3a8a',
        border: '1px solid #3b82f6',
        borderRadius: '8px',
        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        p: 2,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        maxWidth: { xs: '95vw', sm: '80vw', md: '500px' },
        minWidth: { xs: 'calc(100vw - 32px)', sm: '350px' },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{
            color: '#ffffff',
            lineHeight: 1.5,
            fontSize: '0.875rem',
            fontWeight: 500,
          }}
        >
          A new version of Runestone is ready.
        </Typography>
      </Box>
      <Button
        size="small"
        onClick={() => setDismissed(true)}
        sx={{
          color: 'rgba(255, 255, 255, 0.7)',
          '&:hover': {
            color: '#ffffff',
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          },
        }}
      >
        Later
      </Button>
      <Button
        size="small"
        variant="contained"
        startIcon={<Refresh />}
        onClick={handleReload}
        sx={{
          backgroundColor: '#38e07b',
          color: '#060b26',
          fontWeight: 700,
          '&:hover': { backgroundColor: '#5af09a' },
        }}
      >
        Reload
      </Button>
    </Box>
  );
};

export default PwaUpdatePrompt;
