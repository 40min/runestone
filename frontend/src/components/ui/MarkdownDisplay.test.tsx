import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MarkdownDisplay from './MarkdownDisplay';
import * as markdownParser from '../../utils/markdownParser';

// Mock the markdown parser
vi.mock('../../utils/markdownParser', () => ({
  parseMarkdown: vi.fn((content: string) => `<p>${content}</p>`),
}));

describe('MarkdownDisplay', () => {
  it('should render markdown content', () => {
    const markdownContent = '# Test Header\n\nSome content';

    const { container } = render(<MarkdownDisplay markdownContent={markdownContent} />);

    const markdownDiv = container.querySelector('.markdown-content');
    expect(markdownDiv).not.toBeNull();
    expect(markdownDiv?.className).toContain('markdown-content');
  });

  it('should call parseMarkdown with the provided content', () => {
    const markdownContent = 'Test content';

    render(<MarkdownDisplay markdownContent={markdownContent} />);

    expect(markdownParser.parseMarkdown).toHaveBeenCalledWith(markdownContent);
  });

  it('should render empty content', () => {
    const { container } = render(<MarkdownDisplay markdownContent="" />);

    const markdownDiv = container.querySelector('.markdown-content');
    expect(markdownDiv).not.toBeNull();
  });
});
