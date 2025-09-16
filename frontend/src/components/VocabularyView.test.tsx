/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { vi } from 'vitest';

// Mock the useVocabulary hook
vi.mock('../hooks/useVocabulary', () => ({
  default: vi.fn(),
}));

import VocabularyView from "./VocabularyView";
import useVocabulary from '../hooks/useVocabulary';

const mockUseVocabulary = vi.mocked(useVocabulary);

describe("VocabularyView", () => {
  it("renders loading state", () => {
    mockUseVocabulary.mockReturnValue({
      vocabulary: [],
      loading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders error state", () => {
    const errorMessage = "Failed to fetch vocabulary";
    mockUseVocabulary.mockReturnValue({
      vocabulary: [],
      loading: false,
      error: errorMessage,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it("renders empty state when no vocabulary is saved", () => {
    mockUseVocabulary.mockReturnValue({
      vocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText("Saved Vocabulary")).toBeInTheDocument();
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
        created_at: "2023-10-27T10:00:00Z",
      },
      {
        id: 2,
        user_id: 1,
        word_phrase: "bra",
        translation: "good",
        example_phrase: null,
        created_at: "2023-10-28T10:05:00Z",
      },
    ];

    mockUseVocabulary.mockReturnValue({
      vocabulary: mockVocabulary,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText("Saved Vocabulary")).toBeInTheDocument();

    // Check table headers
    expect(screen.getByText("Swedish")).toBeInTheDocument();
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Example Phrase")).toBeInTheDocument();
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
        created_at: "2023-10-27T10:00:00Z",
      },
    ];

    mockUseVocabulary.mockReturnValue({
      vocabulary: mockVocabulary,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<VocabularyView />);

    // Should display dash for null example_phrase
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});