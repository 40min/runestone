import { marked } from 'marked';
import DOMPurify from 'dompurify';

// Configure marked options for better parsing
marked.setOptions({
  gfm: true, // GitHub Flavored Markdown
  breaks: false, // Don't add <br> on single line breaks
  pedantic: false,
});

/**
 * Preprocesses markdown to fix common parsing issues:
 * 1. Prevents consecutive numbered lists from merging
 * 2. Handles bullet points that aren't meant to be nested lists
 */
const preprocessMarkdown = (markdown: string): string => {
  const lines = markdown.split('\n');
  const result: string[] = [];
  let previousLineWasNumberedItem = false;
  let previousLineNumber = 0;

  for (let i = 0; i < lines.length; i++) {
    const currentLine = lines[i];
    const trimmedLine = currentLine.trim();

    // Check if current line is a numbered list item (e.g., "1. ", "2. ", etc.)
    const numberedListMatch = trimmedLine.match(/^(\d+)\.\s/);
    const isNumberedListItem = numberedListMatch !== null;
    const currentLineNumber = numberedListMatch ? parseInt(numberedListMatch[1], 10) : 0;

    // Check if current line starts with a bullet point
    const startsWithBullet = /^-\s/.test(trimmedLine);

    // If this is a numbered list item starting with "1." and the previous line was
    // a numbered list item with a different number, insert a separator
    if (isNumberedListItem && currentLineNumber === 1 && previousLineWasNumberedItem && previousLineNumber > 1) {
      result.push('<div></div>'); // Empty div acts as list separator
    }

    // If the line starts with "number. -", it's actually a numbered item followed by dialogue
    // We need to escape the dash to prevent it from being parsed as a nested list
    if (numberedListMatch && trimmedLine.match(/^\d+\.\s*-\s/)) {
      // Replace "1. - text" with "1. \- text" to escape the dash
      result.push(currentLine.replace(/^(\s*)(\d+\.\s*)-\s/, '$1$2\\- '));
    } else if (startsWithBullet && previousLineWasNumberedItem) {
      // If a bullet follows a numbered item and isn't indented much, it's likely dialogue
      // Convert it to escaped dash to prevent list nesting
      const leadingSpaces = currentLine.match(/^(\s*)/)?.[1] || '';
      if (leadingSpaces.length <= 3) {
        result.push(leadingSpaces + '\\' + trimmedLine);
      } else {
        result.push(currentLine);
      }
    } else {
      result.push(currentLine);
    }

    // Track state for next iteration
    previousLineWasNumberedItem = isNumberedListItem;
    previousLineNumber = currentLineNumber;
  }

  return result.join('\n');
};

/**
 * Parses markdown text into sanitized HTML.
 * @param markdown - The markdown text to parse
 * @returns Sanitized HTML string
 */
export const parseMarkdown = (markdown: string): string => {
  const preprocessed = preprocessMarkdown(markdown);
  const rawHtml = marked.parse(preprocessed) as string;
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'a', 'code', 'pre', 'blockquote', 'hr', 'del', 'span', 'div'
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  });
};
