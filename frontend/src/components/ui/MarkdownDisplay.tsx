import React from 'react';
import { Box } from '@mui/material';
import { parseMarkdown } from '../../utils/markdownParser';

interface MarkdownDisplayProps {
  markdownContent: string;
}

const MarkdownDisplay: React.FC<MarkdownDisplayProps> = ({ markdownContent }) => {
  return (
    <Box
      sx={{ color: 'white' }}
      className="markdown-content"
      dangerouslySetInnerHTML={{
        __html: parseMarkdown(markdownContent),
      }}
    />
  );
};

export default MarkdownDisplay;
