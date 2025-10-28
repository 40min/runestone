import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import GrammarView from "./GrammarView";

// Mock the useGrammar hook
const mockUseGrammar = vi.fn();
vi.mock("../hooks/useGrammar", () => ({
  default: () => mockUseGrammar(),
}));

describe("GrammarView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render loading state initially", () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      loading: true,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText("Grammar Cheatsheets")).toBeInTheDocument();
    expect(screen.getByText("Available Cheatsheets")).toBeInTheDocument();
  });

  it("should render General category cheatsheets at root level", () => {
    const mockCheatsheets = [
      {
        filename: "pronunciation.md",
        title: "Pronunciation",
        category: "General",
      },
      {
        filename: "swedish_adjectives.md",
        title: "Swedish Adjectives",
        category: "General",
      },
      {
        filename: "adjectiv-komparation.md",
        title: "Adjectiv Komparation",
        category: "adjectives",
      },
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

    // General category cheatsheets should be at root level (not in a collapsible section)
    expect(screen.getByText("Pronunciation")).toBeInTheDocument();
    expect(screen.getByText("Swedish Adjectives")).toBeInTheDocument();

    // Category should be rendered as a collapsible section
    expect(screen.getByText("adjectives")).toBeInTheDocument();
  });

  it("should render categories as collapsible sections", () => {
    const mockCheatsheets = [
      {
        filename: "pronunciation.md",
        title: "Pronunciation",
        category: "General",
      },
      {
        filename: "adjectiv-komparation.md",
        title: "Adjectiv Komparation",
        category: "adjectives",
      },
      { filename: "hjalpverb.md", title: "Hjalpverb", category: "verbs" },
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

    // Categories should be rendered with bold text
    const adjectivesCategory = screen.getByText("adjectives");
    const verbsCategory = screen.getByText("verbs");

    expect(adjectivesCategory).toBeInTheDocument();
    expect(verbsCategory).toBeInTheDocument();

    // Cheatsheets should not be visible initially (collapsed) - check for hidden state
    const adjectivCheatsheet = screen.getByText("Adjectiv Komparation");
    const verbCheatsheet = screen.getByText("Hjalpverb");

    // The elements exist in DOM but their parent Collapse should have height 0
    const adjectivParent = adjectivCheatsheet.closest(".MuiCollapse-root");
    const verbParent = verbCheatsheet.closest(".MuiCollapse-root");

    expect(adjectivParent).toHaveStyle({ height: "0px" });
    expect(verbParent).toHaveStyle({ height: "0px" });
  });

  it("should expand and collapse categories when clicked", async () => {
    const mockCheatsheets = [
      {
        filename: "adjectiv-komparation.md",
        title: "Adjectiv Komparation",
        category: "adjectives",
      },
      { filename: "hjalpverb.md", title: "Hjalpverb", category: "verbs" },
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

    // Initially, cheatsheets should be collapsed
    const adjectivCheatsheet = screen.getByText("Adjectiv Komparation");
    let collapseParent = adjectivCheatsheet.closest(".MuiCollapse-root");
    expect(collapseParent).toHaveStyle({ height: "0px" });

    // Click to expand the adjectives category
    const adjectivesCategory = screen.getByText("adjectives");
    fireEvent.click(adjectivesCategory);

    // Now the cheatsheet should be visible (height auto or specific value)
    await waitFor(() => {
      collapseParent = adjectivCheatsheet.closest(".MuiCollapse-root");
      expect(collapseParent).not.toHaveStyle({ height: "0px" });
    });

    // Click again to collapse
    fireEvent.click(adjectivesCategory);

    // Cheatsheet should be hidden again
    await waitFor(() => {
      collapseParent = adjectivCheatsheet.closest(".MuiCollapse-root");
      expect(collapseParent).toHaveStyle({ height: "0px" });
    });
  });

  it("should display cheatsheets within their categories when expanded", async () => {
    const mockCheatsheets = [
      {
        filename: "pronunciation.md",
        title: "Pronunciation",
        category: "General",
      },
      {
        filename: "adjectiv-komparation.md",
        title: "Adjectiv Komparation",
        category: "adjectives",
      },
      { filename: "hjalpverb.md", title: "Hjalpverb", category: "verbs" },
      { filename: "verb-forms.md", title: "Verb Forms", category: "verbs" },
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

    // Expand verbs category
    const verbsCategory = screen.getByText("verbs");
    fireEvent.click(verbsCategory);

    // Both verb cheatsheets should be visible
    await waitFor(() => {
      const hjalpverb = screen.getByText("Hjalpverb");
      const verbsCollapse = hjalpverb.closest(".MuiCollapse-root");
      expect(verbsCollapse).not.toHaveStyle({ height: "0px" });
    });

    // Adjectives cheatsheet should still be collapsed
    const adjectivCheatsheet = screen.getByText("Adjectiv Komparation");
    const adjectivCollapse = adjectivCheatsheet.closest(".MuiCollapse-root");
    expect(adjectivCollapse).toHaveStyle({ height: "0px" });
  });

  it("should render error state", () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      loading: false,
      error: "Test error",
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText("Test error")).toBeInTheDocument();
  });

  it("should handle cheatsheet selection from General category", async () => {
    const mockFetchCheatsheetContent = vi.fn();
    const mockCheatsheets = [
      {
        filename: "pronunciation.md",
        title: "Pronunciation",
        category: "General",
      },
    ];
    const mockSelectedCheatsheet = { content: "# Pronunciation Guide" };

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: mockSelectedCheatsheet,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: mockFetchCheatsheetContent,
    });

    render(<GrammarView />);

    const listItem = screen.getByText("Pronunciation");
    fireEvent.click(listItem);

    await waitFor(() => {
      expect(mockFetchCheatsheetContent).toHaveBeenCalledWith(
        "pronunciation.md"
      );
    });
  });

  it("should handle cheatsheet selection from categorized section", async () => {
    const mockFetchCheatsheetContent = vi.fn();
    const mockCheatsheets = [
      {
        filename: "adjectiv-komparation.md",
        title: "Adjectiv Komparation",
        category: "adjectives",
      },
    ];
    const mockSelectedCheatsheet = { content: "# Adjectiv Komparation" };

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: mockSelectedCheatsheet,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: mockFetchCheatsheetContent,
    });

    render(<GrammarView />);

    // First expand the category
    const adjectivesCategory = screen.getByText("adjectives");
    fireEvent.click(adjectivesCategory);

    // Then click the cheatsheet
    await waitFor(() => {
      const cheatsheet = screen.getByText("Adjectiv Komparation");
      fireEvent.click(cheatsheet);
    });

    await waitFor(() => {
      expect(mockFetchCheatsheetContent).toHaveBeenCalledWith(
        "adjectiv-komparation.md"
      );
    });
  });

  it("should render selected cheatsheet content", async () => {
    const mockCheatsheets = [
      {
        filename: "pronunciation.md",
        title: "Pronunciation",
        category: "General",
      },
    ];
    const mockSelectedCheatsheet = { content: "# Test Content" };

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
    const listItem = screen.getByText("Pronunciation");
    fireEvent.click(listItem);

    // Wait for the content to be rendered
    await waitFor(() => {
      const markdownDiv = container.querySelector(".markdown-content");
      expect(markdownDiv).not.toBeNull();
    });
  });

  it("should show loading spinner when fetching content", () => {
    const mockCheatsheets = [
      {
        filename: "pronunciation.md",
        title: "Pronunciation",
        category: "General",
      },
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

    // When no cheatsheet is selected, should show the placeholder text
    expect(
      screen.getByText("Select a cheatsheet from the list to view its content.")
    ).toBeInTheDocument();
  });

  it("should sort categories alphabetically", () => {
    const mockCheatsheets = [
      { filename: "verb1.md", title: "Verb 1", category: "verbs" },
      { filename: "adj1.md", title: "Adj 1", category: "adjectives" },
      { filename: "noun1.md", title: "Noun 1", category: "nouns" },
    ];

    mockUseGrammar.mockReturnValue({
      cheatsheets: mockCheatsheets,
      selectedCheatsheet: null,
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
    });

    const { container } = render(<GrammarView />);

    // Get all category buttons
    const categoryButtons = container.querySelectorAll('[role="button"]');
    const categoryTexts = Array.from(categoryButtons)
      .map((button) => button.textContent)
      .filter(
        (text) => text && ["adjectives", "nouns", "verbs"].includes(text)
      );

    // Should be in alphabetical order
    expect(categoryTexts).toEqual(["adjectives", "nouns", "verbs"]);
  });
});
