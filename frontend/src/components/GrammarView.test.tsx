import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GrammarView from './GrammarView';

// Mock the useGrammar hook
const mockUseGrammar = vi.fn();
vi.mock('../hooks/useGrammar', () => ({
  default: () => mockUseGrammar(),
}));

describe('GrammarView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render loading state initially', () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      loading: true,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText('Grammar Cheatsheets')).toBeInTheDocument();
    expect(screen.getByText('Available Cheatsheets')).toBeInTheDocument();
  });

  it('should render cheatsheet list', () => {
    const mockCheatsheets = [
      { filename: 'test1.md', title: 'Test 1' },
      { filename: 'test2.md', title: 'Test 2' },
    ];

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: null,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText('Test 1')).toBeInTheDocument();
    expect(screen.getByText('Test 2')).toBeInTheDocument();
    expect(screen.getByText('Select a cheatsheet from the list to view its content.')).toBeInTheDocument();
  });

  it('should render error state', () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      loading: false,
      error: 'Test error',
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText('Test error')).toBeInTheDocument();
  });

  it('should handle cheatsheet selection', async () => {
    const mockFetchCheatsheetContent = vi.fn();
    const mockCheatsheets = [{ filename: 'test.md', title: 'Test' }];
    const mockSelectedCheatsheet = { content: '# Test Content' };

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: mockSelectedCheatsheet,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: mockFetchCheatsheetContent,
    });

    render(<GrammarView />);

    const listItem = screen.getByText('Test');
    fireEvent.click(listItem);

    await waitFor(() => {
      expect(mockFetchCheatsheetContent).toHaveBeenCalledWith('test.md');
    });
  });

  it('should render selected cheatsheet content', async () => {
    const mockCheatsheets = [{ filename: 'test.md', title: 'Test' }];
    const mockSelectedCheatsheet = { content: '# Test Content' };

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: mockSelectedCheatsheet,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn().mockResolvedValue(undefined),
    });

    const { container } = render(<GrammarView />);

    // Click on the cheatsheet to select it
    const listItem = screen.getByText('Test');
    fireEvent.click(listItem);

    // Wait for the content to be rendered
    await waitFor(() => {
      const markdownDiv = container.querySelector('.markdown-content');
      expect(markdownDiv).not.toBeNull();
    });
  });

  it('should show loading spinner when fetching content', () => {
    const mockCheatsheets = [{ filename: 'test.md', title: 'Test' }];

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: null,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    render(<GrammarView />);

    // When no cheatsheet is selected, should show the placeholder text
    expect(screen.getByText('Select a cheatsheet from the list to view its content.')).toBeInTheDocument();
  });
});
