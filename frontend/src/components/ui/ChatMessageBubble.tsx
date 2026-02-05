import React from 'react';
import { Box, Link, Typography } from '@mui/material';

interface ChatMessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: { title: string; url: string; date: string }[] | null;
}

export const ChatMessageBubble: React.FC<ChatMessageBubbleProps> = ({ role, content, sources }) => {
  const hasSources = role === 'assistant' && sources && sources.length > 0;

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: role === 'user' ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Box
        sx={{
          maxWidth: { xs: '85%', md: '70%' },
          padding: '12px 16px',
          borderRadius: '12px',
          backgroundColor:
            role === 'user' ? 'rgba(147, 51, 234, 0.2)' : 'rgba(58, 45, 74, 0.6)',
          border:
            role === 'user'
              ? '1px solid rgba(147, 51, 234, 0.3)'
              : '1px solid rgba(147, 51, 234, 0.1)',
        }}
      >
        <Typography
          sx={{
            color: 'white',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {content}
        </Typography>
        {hasSources && (
          <Box sx={{ mt: 1.5 }}>
            <Typography sx={{ color: '#c4b5fd', fontSize: '0.75rem', mb: 0.5 }}>
              Sources
            </Typography>
            <Box
              component="ul"
              sx={{
                listStyle: 'none',
                p: 0,
                m: 0,
                display: 'grid',
                gap: 0.75,
              }}
            >
              {sources.map((source) => (
                <Box component="li" key={source.url}>
                  <Link
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    underline="hover"
                    sx={{ color: '#f3f4f6', fontSize: '0.9rem', fontWeight: 500 }}
                  >
                    {source.title}
                  </Link>
                  <Typography sx={{ color: '#9ca3af', fontSize: '0.7rem', mt: 0.25 }}>
                    {source.date}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
};
