/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from 'vitest';

// Mock the useVocabulary hook
vi.mock('../hooks/useVocabulary', () => ({
  default: vi.fn(),
  useVocabularyStats: vi.fn(() => ({
    stats: {
      words_in_learn_count: 3,
      words_skipped_count: 2,
      overall_words_count: 5,
      words_prioritized_count: 1,
    },
    loading: false,
    error: null,
    refetch: vi.fn(),
  })),
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

// Mock the useApi hook
vi.mock('../utils/api', () => ({
  useApi: vi.fn(() => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    apiClient: vi.fn(),
  })),
}));

vi.mock("./AddEditVocabularyModal", () => ({
  default: ({
    open,
    onSave,
    onDelete,
  }: {
    open: boolean;
    onSave: (item: Record<string, unknown>) => Promise<void>;
    onDelete: () => Promise<void>;
  }) =>
    open ? (
      <div>
        <button type="button" onClick={() => void onSave({ word_phrase: "updated-word" })}>
          Mock Save
        </button>
        <button type="button" onClick={() => void onDelete()}>
          Mock Delete
        </button>
      </div>
    ) : null,
}));

import VocabularyView from "./VocabularyView";
import { useRecentVocabulary, useVocabularyStats } from '../hooks/useVocabulary';
import { AuthProvider } from '../context/AuthContext';

const mockUseRecentVocabulary = vi.mocked(useRecentVocabulary);
const mockUseVocabularyStats = vi.mocked(useVocabularyStats);

const renderWithAuthProvider = (component: React.ReactElement) => {
  return render(
    <AuthProvider>
      {component}
    </AuthProvider>
  );
};

describe("VocabularyView", () => {
  beforeEach(() => {
    mockUseRecentVocabulary.mockClear();
    mockUseVocabularyStats.mockClear();
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

    renderWithAuthProvider(<VocabularyView />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders inline loading indicator after initial load", async () => {
    // Start with loading=true to simulate initial load
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

    const { rerender } = renderWithAuthProvider(<VocabularyView />);

    // Should show full-page spinner during initial load
    expect(screen.getByRole("progressbar")).toBeInTheDocument();

    // Complete initial load with data
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [{
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
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

    rerender(<VocabularyView />);

    // Wait for initial load to complete
    await waitFor(() => {
      expect(screen.getByText("hej")).toBeInTheDocument();
    });

    // Now simulate a search that triggers loading after initial load
    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [{
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: "2023-10-27T10:00:00Z",
        updated_at: "2023-10-27T10:00:00Z",
      }],
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

    renderWithAuthProvider(<VocabularyView />);

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

    renderWithAuthProvider(<VocabularyView />);

    expect(screen.getByText("Words Learning")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Words Skipped")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Overall Words")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Prioritised Words")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Recent Vocabulary")).toBeInTheDocument();
    expect(screen.getByText("No vocabulary saved yet.")).toBeInTheDocument();
    expect(screen.getByText("Analyze some text and save vocabulary items to see them here.")).toBeInTheDocument();
  });

  it("renders vocabulary stats error without blocking the table view", () => {
    mockUseVocabularyStats.mockReturnValue({
      stats: null,
      loading: false,
      error: "Failed to fetch vocabulary stats",
      refetch: vi.fn(),
    });
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

    renderWithAuthProvider(<VocabularyView />);

    expect(screen.getByText("Failed to fetch vocabulary stats")).toBeInTheDocument();
    expect(screen.getByText("Recent Vocabulary")).toBeInTheDocument();
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

    renderWithAuthProvider(<VocabularyView />);

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

    renderWithAuthProvider(<VocabularyView />);

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

    renderWithAuthProvider(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    const searchButton = screen.getByRole("button", { name: /search/i });

    fireEvent.change(searchInput, { target: { value: 'test' } });
    fireEvent.click(searchButton);

    expect(mockUseRecentVocabulary).toHaveBeenCalledWith('test', false);
  });

  it("renders precise search checkbox and toggles hook parameter", () => {
    const mockHookReturn = {
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
    };

    mockUseRecentVocabulary.mockReturnValue(mockHookReturn);

    renderWithAuthProvider(<VocabularyView />);

    const checkbox = screen.getByLabelText("Precise search");
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);
    expect(mockUseRecentVocabulary).toHaveBeenLastCalledWith("", true);

    fireEvent.click(checkbox);
    expect(mockUseRecentVocabulary).toHaveBeenLastCalledWith("", false);
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

    renderWithAuthProvider(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    fireEvent.change(searchInput, { target: { value: 'hello' } });

    // Should call immediately when >3 chars
    await waitFor(() => {
      expect(mockUseRecentVocabulary).toHaveBeenCalledWith('hello', false);
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

    renderWithAuthProvider(<VocabularyView />);

    const searchInput = screen.getByPlaceholderText("Search vocabulary...");
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    // Should trigger search immediately since >3 chars
    await waitFor(() => {
      expect(screen.getByText("No vocabulary matches your search.")).toBeInTheDocument();
      expect(screen.getByText("Try a different search term.")).toBeInTheDocument();
    });
    expect(mockUseRecentVocabulary).toHaveBeenCalledWith('nonexistent', false);
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
        learned_times: 5,
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
        learned_times: 0,
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

    renderWithAuthProvider(<VocabularyView />);

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
        learned_times: 2,
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

    renderWithAuthProvider(<VocabularyView />);

    // Should display dash for null example_phrase and null extra_info
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("refetches stats after saving an existing vocabulary item", async () => {
    const updateVocabularyItem = vi.fn().mockResolvedValue(undefined);
    const refetchStats = vi.fn().mockResolvedValue(undefined);

    mockUseVocabularyStats.mockReturnValue({
      stats: {
        words_in_learn_count: 3,
        words_skipped_count: 2,
        overall_words_count: 5,
        words_prioritized_count: 1,
      },
      loading: false,
      error: null,
      refetch: refetchStats,
    });

    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: true,
      editingItem: {
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        priority_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: "2023-10-27T10:00:00Z",
        updated_at: "2023-10-27T10:00:00Z",
      },
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem,
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem: vi.fn().mockResolvedValue(undefined),
    });

    renderWithAuthProvider(<VocabularyView />);
    fireEvent.click(screen.getByRole("button", { name: "Mock Save" }));

    await waitFor(() => {
      expect(updateVocabularyItem).toHaveBeenCalledWith(1, { word_phrase: "updated-word" });
      expect(refetchStats).toHaveBeenCalledTimes(1);
    });
  });

  it("refetches stats after deleting an existing vocabulary item", async () => {
    const deleteVocabularyItem = vi.fn().mockResolvedValue(undefined);
    const refetchStats = vi.fn().mockResolvedValue(undefined);

    mockUseVocabularyStats.mockReturnValue({
      stats: {
        words_in_learn_count: 3,
        words_skipped_count: 2,
        overall_words_count: 5,
        words_prioritized_count: 1,
      },
      loading: false,
      error: null,
      refetch: refetchStats,
    });

    mockUseRecentVocabulary.mockReturnValue({
      recentVocabulary: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
      isEditModalOpen: true,
      editingItem: {
        id: 1,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: null,
        extra_info: null,
        in_learn: false,
        priority_learn: false,
        last_learned: null,
        learned_times: 0,
        created_at: "2023-10-27T10:00:00Z",
        updated_at: "2023-10-27T10:00:00Z",
      },
      openEditModal: vi.fn(),
      closeEditModal: vi.fn(),
      updateVocabularyItem: vi.fn().mockResolvedValue(undefined),
      createVocabularyItem: vi.fn(),
      deleteVocabularyItem,
    });

    renderWithAuthProvider(<VocabularyView />);
    fireEvent.click(screen.getByRole("button", { name: "Mock Delete" }));

    await waitFor(() => {
      expect(deleteVocabularyItem).toHaveBeenCalledWith(1);
      expect(refetchStats).toHaveBeenCalledTimes(1);
    });
  });
});
