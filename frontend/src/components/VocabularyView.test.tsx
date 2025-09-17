/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { vi } from 'vitest';

// Mock the useVocabulary hook
vi.mock('../hooks/useVocabulary', () => ({
  default: vi.fn(),
  useRecentVocabulary: vi.fn(),
}));

import VocabularyView from "./VocabularyView";
import { useRecentVocabulary } from '../hooks/useVocabulary';

const mockUseRecentVocabulary = vi.mocked(useRecentVocabulary);

describe("VocabularyView", () => {
  it("renders loading state", () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders error state", () => {
    const errorMessage = "Failed to fetch vocabulary";
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: errorMessage,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it("renders empty state when no vocabulary is saved", () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText("Recent Vocabulary")).toBeInTheDocument();
    expect(screen.getByText("No vocabulary saved yet.")).toBeInTheDocument();
    expect(screen.getByText("Analyze some text and save vocabulary items to see them here.")).toBeInTheDocument();
  });

  it("renders vocabulary table with data", () => {
    const mockVocabulary = [
      {
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: "Hej, hur mår du?",
        in_learn: true,
        showed_times: 5,
        created_at: "2023-10-27T10:00:00Z",
      },
      {
        id: 2,
        user_id: 1,
        word_phrase: "bra",
        translation: "good",
        example_phrase: null,
        in_learn: false,
        showed_times: 0,
        created_at: "2023-10-28T10:05:00Z",
      },
    ];

    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: mockVocabulary,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText("Recent Vocabulary")).toBeInTheDocument();

    // Check table headers
    expect(screen.getByText("Swedish")).toBeInTheDocument();
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Example Phrase")).toBeInTheDocument();
    expect(screen.getByText("In Learning")).toBeInTheDocument();
    expect(screen.getByText("Shown Times")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();

    // Check vocabulary data
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("Hej, hur mår du?")).toBeInTheDocument();

    expect(screen.getByText("bra")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // null example_phrase should show dash

    // Check dates are formatted
    expect(screen.getByText("10/27/2023")).toBeInTheDocument();
    expect(screen.getByText("10/28/2023")).toBeInTheDocument();
  });

  it("handles null example_phrase correctly", () => {
    const mockVocabulary = [
      {
        id: 1,
        user_id: 1,
        word_phrase: "test",
        translation: "test translation",
        example_phrase: null,
        in_learn: true,
        showed_times: 2,
        created_at: "2023-10-27T10:00:00Z",
      },
    ];

    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: mockVocabulary,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    // Should display dash for null example_phrase
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});