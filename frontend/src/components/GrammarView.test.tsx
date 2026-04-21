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
    // GrammarView now syncs selection into the URL; reset between tests to avoid cross-test leakage.
    window.history.replaceState({}, "", "/");
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
      const cheatsheet = screen.getByRole("button", {
        name: "Adjectiv Komparation",
      });
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
      screen.getByText("Search grammar cheatsheets")
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

  it("copies selected cheatsheet markdown to clipboard", async () => {
    const mockClipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    Object.assign(navigator, { clipboard: mockClipboard });

    mockUseGrammar.mockReturnValue({
      cheatsheets: [
        {
          filename: "pronunciation.md",
          title: "Pronunciation",
          category: "General",
        },
      ],
      selectedCheatsheet: { content: "# Pronunciation Guide" },
      loading: false,
      error: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn().mockResolvedValue(undefined),
    });

    render(<GrammarView />);
    fireEvent.click(screen.getByText("Pronunciation"));
    fireEvent.click(await screen.findByRole("button", { name: "Copy markdown" }));

    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith("# Pronunciation Guide");
    });
  });

  it("renders grammar search input in the default empty state", () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      searchResults: [],
      loading: false,
      error: null,
      searchLoading: false,
      searchError: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
      searchGrammar: vi.fn(),
      clearSearch: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByPlaceholderText("Search grammar topics...")).toBeInTheDocument();
  });

  it("submits grammar search from the empty state", async () => {
    const mockSearchGrammar = vi.fn().mockResolvedValue(undefined);

    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      searchResults: [],
      loading: false,
      error: null,
      searchLoading: false,
      searchError: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
      searchGrammar: mockSearchGrammar,
      clearSearch: vi.fn(),
    });

    render(<GrammarView />);

    fireEvent.change(screen.getByPlaceholderText("Search grammar topics..."), {
      target: { value: "adjective comparison" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(mockSearchGrammar).toHaveBeenCalledWith("adjective comparison");
    });
  });

  it("renders grammar search results", () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      searchResults: [
        {
          title: "Adjective comparison rules",
          url: "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation",
          path: "adjectives/komparation.md",
        },
      ],
      loading: false,
      error: null,
      searchLoading: false,
      searchError: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
      searchGrammar: vi.fn(),
      clearSearch: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText("Adjective comparison rules")).toBeInTheDocument();
    expect(screen.getByText("adjectives/komparation.md")).toBeInTheDocument();
  });

  it("opens a grammar search result and updates the URL", async () => {
    const mockFetchCheatsheetContent = vi.fn().mockResolvedValue(undefined);

    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      searchResults: [
        {
          title: "Verb forms",
          url: "http://localhost:5173/?view=grammar&cheatsheet=verbs/verb-forms",
          path: "verbs/verb-forms.md",
        },
      ],
      loading: false,
      error: null,
      searchLoading: false,
      searchError: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: mockFetchCheatsheetContent,
      searchGrammar: vi.fn(),
      clearSearch: vi.fn(),
    });

    render(<GrammarView />);
    fireEvent.click(screen.getByRole("button", { name: /Verb forms/ }));

    await waitFor(() => {
      expect(mockFetchCheatsheetContent).toHaveBeenCalledWith("verbs/verb-forms.md");
    });
    expect(window.location.search).toContain("view=grammar");
    expect(window.location.search).toContain("cheatsheet=verbs%2Fverb-forms");
  });

  it("renders no-result message after an empty grammar search", async () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      searchResults: [],
      loading: false,
      error: null,
      searchLoading: false,
      searchError: null,
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
      searchGrammar: vi.fn().mockResolvedValue(undefined),
      clearSearch: vi.fn(),
    });

    render(<GrammarView />);

    fireEvent.change(screen.getByPlaceholderText("Search grammar topics..."), {
      target: { value: "nope" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("No matching grammar pages found.")).toBeInTheDocument();
  });

  it("renders grammar search errors separately", () => {
    mockUseGrammar.mockReturnValue({
      cheatsheets: [],
      selectedCheatsheet: null,
      searchResults: [],
      loading: false,
      error: null,
      searchLoading: false,
      searchError: "Failed to search grammar cheatsheets",
      fetchCheatsheets: vi.fn(),
      fetchCheatsheetContent: vi.fn(),
      searchGrammar: vi.fn(),
      clearSearch: vi.fn(),
    });

    render(<GrammarView />);

    expect(screen.getByText("Failed to search grammar cheatsheets")).toBeInTheDocument();
  });
});
