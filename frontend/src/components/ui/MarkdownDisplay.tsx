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
        // parseMarkdown is the single DOMPurify sanitization boundary.
        __html: parseMarkdown(markdownContent), // nosemgrep
      }}
    />
  );
};

export default MarkdownDisplay;
