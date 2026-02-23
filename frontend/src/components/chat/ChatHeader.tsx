import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import { NewChatButton } from '../ui';
import PsychologyIcon from '@mui/icons-material/Psychology';

interface ChatHeaderProps {
  title: string;
  subtitle: string;
  onNewChat: () => void;
  onOpenMemory: () => void;
  isLoading: boolean;
  hasMessages: boolean;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  title,
  subtitle,
  onNewChat,
  onOpenMemory,
  isLoading,
  hasMessages,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: { xs: 1, md: 2 },
        gap: 1,
      }}
    >
      <Box>
        <Typography
          variant="h5"
          sx={{
            color: 'white',
            fontWeight: 'bold',
            mb: 0.5,
            fontSize: { xs: '1.25rem', md: '1.5rem' },
          }}
        >
          {title}
        </Typography>
        <Typography
          sx={{
            display: { xs: 'none', md: 'block' },
            color: '#9ca3af',
            fontSize: '0.875rem',
          }}
        >
          {subtitle}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Tooltip title="Student Memory">
          <IconButton
            onClick={onOpenMemory}
            sx={{
              color: 'var(--primary-color)',
              bgcolor: 'rgba(59, 130, 246, 0.1)',
              '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.2)' }
            }}
          >
            <PsychologyIcon />
          </IconButton>
        </Tooltip>
        <NewChatButton
          onClick={onNewChat}
          isLoading={isLoading}
          hasMessages={hasMessages}
        />
      </Box>
    </Box>
  );
};
