/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from 'vitest';

// Mock the useVocabulary hook
vi.mock('../hooks/useVocabulary', () => ({
  default: vi.fn(),
  useRecentVocabulary: vi.fn(() => ({
    recentVocabulary: [],
    loading: false,
    error: null,
    refetch: vi.fn(),
    isEditModalOpen: false,
    editingItem: null,
    openEditModal: vi.fn(),
    closeEditModal: vi.fn(),
    updateVocabularyItem: vi.fn(),
    createVocabularyItem: vi.fn(),
    deleteVocabularyItem: vi.fn(),
  })),
}));

import VocabularyView from "./VocabularyView";
import { useRecentVocabulary } from '../hooks/useVocabulary';

const mockUseRecentVocabulary = vi.mocked(useRecentVocabulary);

describe("VocabularyView", () => {
  beforeEach(() => {
    mockUseRecentVocabulary.mockClear();
  });

  it("renders loading state on initial load", () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: true,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders inline loading indicator after initial load", async () => {
    // First render with data to complete initial load
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [{
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: null,
        in_learn: false,
        last_learned: null,
        created_at: "2023-10-27T10:00:00Z",
        updated_at: "2023-10-27T10:00:00Z",
      }],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    const { rerender } = render(<VocabularyView />);

    // Now simulate a search that triggers loading
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: true,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    rerender(<VocabularyView />);

    // Should show inline loading text, not full-page spinner
    await waitFor(() => {
      expect(screen.getByText("Loading...")).toBeInTheDocument();
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    });
  });

  it("renders error state", () => {
    const errorMessage = "Failed to fetch vocabulary";
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: errorMessage,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
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
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText("Recent Vocabulary")).toBeInTheDocument();
    expect(screen.getByText("No vocabulary saved yet.")).toBeInTheDocument();
    expect(screen.getByText("Analyze some text and save vocabulary items to see them here.")).toBeInTheDocument();
  });

  it("renders search input", () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    expect(searchInput).toBeInTheDocument();
  });

  it("renders search button", () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    const searchButton = screen.getByRole("button", { name: /search/i });
    expect(searchButton).toBeInTheDocument();
  });

  it("calls useRecentVocabulary when search button is clicked", () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    const searchButton = screen.getByRole("button", { name: /search/i });

    fireEvent.change(searchInput, { target: { value: 'test' } });
    fireEvent.click(searchButton);

    expect(mockUseRecentVocabulary).toHaveBeenCalledWith('test');
  });

  it("calls useRecentVocabulary with search term when >3 characters", async () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    fireEvent.change(searchInput, { target: { value: 'hello' } });

    // Should call immediately when >3 chars
    await waitFor(() => {
      expect(mockUseRecentVocabulary).toHaveBeenCalledWith('hello');
    });
  });

  it("renders empty search state when search returns no results", async () => {
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    // Should trigger search immediately since >3 chars
    await waitFor(() => {
      expect(screen.getByText("No vocabulary matches your search.")).toBeInTheDocument();
      expect(screen.getByText("Try a different search term.")).toBeInTheDocument();
    });
  });

  it("renders vocabulary table with data", () => {
    const mockVocabulary = [
      {
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: "Hej, hur mår du?",
        extra_info: "en-word, noun, base form: hej",
        in_learn: true,
        last_learned: null,
        showed_times: 5,
        created_at: "2023-10-27T10:00:00Z",
        updated_at: "2023-10-27T10:00:00Z",
      },
      {
        id: 2,
        user_id: 1,
        word_phrase: "bra",
        translation: "good",
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        showed_times: 0,
        created_at: "2023-10-28T10:05:00Z",
        updated_at: "2023-10-28T10:05:00Z",
      },
    ];

    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: mockVocabulary,
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    expect(screen.getByText("Recent Vocabulary")).toBeInTheDocument();

    // Check table headers
    expect(screen.getByText("Swedish")).toBeInTheDocument();
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Example Phrase")).toBeInTheDocument();
    expect(screen.getByText("Grammar Info")).toBeInTheDocument();
    expect(screen.getByText("In Learning")).toBeInTheDocument();
    expect(screen.getByText("Last Learned")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();

    // Check vocabulary data
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("Hej, hur mår du?")).toBeInTheDocument();
    expect(screen.getByText("en-word, noun, base form: hej")).toBeInTheDocument();

    expect(screen.getByText("bra")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2); // null example_phrase and null extra_info should show dash

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
        extra_info: null,
        in_learn: true,
        last_learned: null,
        showed_times: 2,
        created_at: "2023-10-27T10:00:00Z",
        updated_at: "2023-10-27T10:00:00Z",
      },
    ];

    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: mockVocabulary,
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: false,
      editingItem: null,
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn(),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn(),
    });

    render(<VocabularyView />);

    // Should display dash for null example_phrase and null extra_info
    expect(screen.getAllByText("—")).toHaveLength(2);
  });
});
