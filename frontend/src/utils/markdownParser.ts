import { marked } from "marked";
import DOMPurify from "dompurify";

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
 * 3. Normalizes numbered items without periods (e.g., "1 text" → "1. text")
 */
const preprocessMarkdown = (markdown: string): string => {
  const lines = markdown.split("\n");
  const result: string[] = [];
  let lastNumberedLineNumber = 0; // Track the last seen numbered line number

  for (let i = 0; i < lines.length; i++) {
    const currentLine = lines[i];
    const trimmedLine = currentLine.trim();

    // Check if current line is a numbered list item with period (e.g., "1. ", "2. ", etc.)
    const numberedListWithPeriodMatch = trimmedLine.match(/^(\d+)\.\s/);

    // Check if current line looks like a numbered list item without period
    // Pattern: number + space + (capital letter OR dash OR common sentence starters)
    // Includes Swedish capital letters (Å, Ä, Ö)
    const numberedListWithoutPeriodMatch = trimmedLine.match(
      /^(\d+)\s+(?=[A-ZÅÄÖ-])/
    );

    let isNumberedListItem = numberedListWithPeriodMatch !== null;
    let currentLineNumber = numberedListWithPeriodMatch
      ? parseInt(numberedListWithPeriodMatch[1], 10)
      : 0;

    // If it's a numbered item without a period, normalize it by adding the period
    let processedLine = currentLine;
    if (!isNumberedListItem && numberedListWithoutPeriodMatch) {
      const lineNumber = parseInt(numberedListWithoutPeriodMatch[1], 10);
      // Convert "1 text" to "1. text" by inserting a period after the number
      const leadingSpaces = currentLine.match(/^(\s*)/)?.[1] || "";
      const restOfLine = currentLine.substring(
        leadingSpaces.length + numberedListWithoutPeriodMatch[1].length
      );
      processedLine = leadingSpaces + lineNumber + "." + restOfLine;
      isNumberedListItem = true;
      currentLineNumber = lineNumber;
    }

    // Check if current line starts with a bullet point
    const startsWithBullet = /^-\s/.test(trimmedLine);

    // If this is a numbered list item and the line number decreased (e.g., 4→1, 3→2),
    // insert a separator to prevent lists from merging
    if (
      isNumberedListItem &&
      lastNumberedLineNumber > 0 &&
      lastNumberedLineNumber > currentLineNumber
    ) {
      result.push("<!-- separator --> "); // Horizontal rule acts as list separator
    }

    // If the line starts with "number. -", it's actually a numbered item followed by dialogue
    // We need to escape the dash to prevent it from being parsed as a nested list
    if (isNumberedListItem && /^\s*\d+\.\s*-\s/.test(processedLine)) {
      // Replace "1. - text" with "1. \- text" to escape the dash
      result.push(processedLine.replace(/^(\s*)(\d+\.\s*)-\s/, "$1$2\\- "));
    } else if (startsWithBullet && lastNumberedLineNumber > 0) {
      // If a bullet follows a numbered item and isn't indented much, it's likely dialogue
      // Convert it to escaped dash to prevent list nesting
      const leadingSpaces = currentLine.match(/^(\s*)/)?.[1] || "";
      if (leadingSpaces.length <= 3) {
        result.push(leadingSpaces + "\\" + trimmedLine);
      } else {
        result.push(currentLine);
      }
    } else {
      result.push(processedLine);
    }

    // Track the last numbered line number (persist across non-numbered lines)
    if (isNumberedListItem) {
      lastNumberedLineNumber = currentLineNumber;
    }
  }

  return result.join("\n");
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
      "p",
      "br",
      "strong",
      "em",
      "u",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "ul",
      "ol",
      "li",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "a",
      "code",
      "pre",
      "blockquote",
      "hr",
      "del",
      "span",
      "div",
    ],
    ALLOWED_ATTR: ["href", "target", "rel", "class"],
  });
};
