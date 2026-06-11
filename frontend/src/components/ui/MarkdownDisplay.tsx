import React from 'react';
import { Box } from '@mui/material';
import DOMPurify from 'dompurify';
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
        __html: DOMPurify.sanitize(parseMarkdown(markdownContent)),
      }}
    />
  );
};

export default MarkdownDisplay;
