import React from 'react';
import { Box, Link, Typography } from '@mui/material';

interface ChatMessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: { title: string; url: string; date: string }[] | null;
}

export const ChatMessageBubble: React.FC<ChatMessageBubbleProps> = ({ role, content, sources }) => {
  const hasSources = role === 'assistant' && sources && sources.length > 0;
  const resolveSafeUrl = (url: string) => {
    try {
      const parsed = new URL(url);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return parsed.toString();
      }
    } catch {
      return null;
    }
    return null;
  };
  const renderContentWithLinks = (text: string): React.ReactNode => {
    if (!text) return text;

    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    const nodes: React.ReactNode[] = [];

    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      const isUrl = index % 2 === 1;
      if (!isUrl) {
        nodes.push(part);
        continue;
      }

      let url = part;
      let trailing = '';
      while (url.length > 0 && /[).,;:!?]/.test(url[url.length - 1])) {
        trailing = url[url.length - 1] + trailing;
        url = url.slice(0, -1);
      }

      const safeUrl = resolveSafeUrl(url);
      if (safeUrl) {
        nodes.push(
          <Link
            key={`link-${index}`}
            href={safeUrl}
            target="_blank"
            rel="noopener noreferrer"
            underline="always"
            sx={{
              color: 'var(--primary-color)',
              textDecorationColor: 'var(--primary-color)',
              fontWeight: 500,
              '&:hover': {
                color: 'var(--primary-color)',
              },
            }}
          >
            {url}
          </Link>
        );
      } else {
        nodes.push(part);
      }

      if (trailing) nodes.push(trailing);
    }

    return nodes;
  };
  const formatDate = (value: string) => {
    if (!value) return value;
    return value.replace(/\.\d+(?=Z|$)/, '');
  };

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
          maxWidth: { xs: '100%', sm: '98%', md: '92%' },
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
          {renderContentWithLinks(content)}
        </Typography>
        {hasSources && (
          <Box sx={{ mt: 1.5 }}>
            <Typography
              sx={(theme) => ({
                color: theme.palette.primary.light,
                fontSize: '0.75rem',
                mb: 0.5,
              })}
            >
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
                  {(() => {
                    const safeUrl = resolveSafeUrl(source.url);
                    return safeUrl ? (
                      <Link
                        href={safeUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        underline="always"
                        sx={{
                          color: 'var(--primary-color)',
                          textDecorationColor: 'var(--primary-color)',
                          fontSize: '0.9rem',
                          fontWeight: 500,
                          '&:hover': {
                            color: 'var(--primary-color)',
                          },
                        }}
                      >
                        {source.title}
                      </Link>
                    ) : (
                      <Typography
                        sx={(theme) => ({
                          color: theme.palette.common.white,
                          fontSize: '0.9rem',
                          fontWeight: 500,
                        })}
                      >
                        {source.title}
                      </Typography>
                    );
                  })()}
                  {source.date && (
                    <Typography
                      sx={(theme) => ({
                        color: theme.palette.grey[300],
                        fontSize: '0.75rem',
                        mt: 0.25,
                      })}
                    >
                      {formatDate(source.date)}
                    </Typography>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
};
