/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import VocabularyStatsModal from "./VocabularyStatsModal";
import { buildLearnedDistributionGradient } from "./vocabulary/visualization";

// ─── Mocks ───────────────────────────────────────────────────────────────────

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    token: null,
    userData: null,
    login: vi.fn(),
    logout: vi.fn(),
    isAuthenticated: () => false,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("../utils/api", () => ({
  useApi: vi.fn(() => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  })),
}));

import { useVocabularyDistribution } from "../hooks/useVocabulary";

vi.mock("../hooks/useVocabulary", () => ({
  useVocabularyDistribution: vi.fn(),
}));

const mockUseDistribution = vi.mocked(useVocabularyDistribution);

// ─── Helpers ─────────────────────────────────────────────────────────────────

const makePriorityDistribution = (counts: number[] = Array(10).fill(0)) =>
  counts.map((count, i) => ({
    priority: i,
    label: `Priority ${i}`,
    count,
  }));

const makeLearnedDistribution = (
  never = 0,
  one10 = 0,
  eleven30 = 0,
  gt30 = 0
) => [
  { label: "Never", count: never },
  { label: "1\u201310", count: one10 },
  { label: "11\u201330", count: eleven30 },
  { label: ">30", count: gt30 },
];

const renderModal = (open = true) =>
  render(<VocabularyStatsModal open={open} onClose={vi.fn()} />);

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("VocabularyStatsModal", () => {
  beforeEach(() => {
    mockUseDistribution.mockReset();
  });

  it("builds the donut gradient from every learned bucket", () => {
    expect(buildLearnedDistributionGradient([50, 25, 15, 10])).toBe(
      "conic-gradient(#6366f1 0% 50%, #22d3ee 50% 75%, #a78bfa 75% 90%, #34d399 90% 100%)"
    );
  });

  it("shows loading spinner while fetching", () => {
    mockUseDistribution.mockReturnValue({ data: null, loading: true, error: null });
    renderModal();
    // LoadingSpinner renders a CircularProgress; check it's present
    expect(document.querySelector("[role='progressbar']")).toBeInTheDocument();
    expect(screen.queryByText("Learning history")).not.toBeInTheDocument();
  });

  it("shows loading spinner before the initial request updates loading state", () => {
    mockUseDistribution.mockReturnValue({
      data: null,
      loading: false,
      error: null,
    });
    renderModal();
    expect(document.querySelector("[role='progressbar']")).toBeInTheDocument();
    expect(screen.queryByText("Learning history")).not.toBeInTheDocument();
  });

  it("shows error message on fetch failure", () => {
    mockUseDistribution.mockReturnValue({
      data: null,
      loading: false,
      error: "Failed to load vocabulary statistics",
    });
    renderModal();
    expect(
      screen.getByText(/failed to load vocabulary statistics/i)
    ).toBeInTheDocument();
    expect(screen.queryByText("Learning history")).not.toBeInTheDocument();
  });

  it("shows empty-state message when all counts are zero", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution(),
        learned_times_distribution: makeLearnedDistribution(),
      },
      loading: false,
      error: null,
    });
    renderModal();
    expect(screen.getByText(/no vocabulary data yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Learning history")).not.toBeInTheDocument();
  });

  it("renders the redesigned statistics sections when data has positive counts", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([5, 0, 0, 0, 0, 0, 0, 0, 0, 2]),
        learned_times_distribution: makeLearnedDistribution(3, 2, 0, 0),
      },
      loading: false,
      error: null,
    });
    renderModal();
    expect(screen.queryByText(/no vocabulary data yet/i)).not.toBeInTheDocument();
    expect(screen.getByText("Learning history")).toBeInTheDocument();
    expect(screen.getByText("Priority distribution")).toBeInTheDocument();
    expect(screen.getByText("words included in these distributions")).toBeInTheDocument();
  });

  it("renders all ten comparison bars including zero-count priorities", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([5, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        learned_times_distribution: makeLearnedDistribution(3, 0, 0, 0),
      },
      loading: false,
      error: null,
    });
    renderModal();
    for (let priority = 0; priority < 10; priority++) {
      expect(screen.getByTestId(`priority-bar-${priority}`)).toBeInTheDocument();
    }
  });

  it("maps highest priority to alert red and lowest priority to green", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([1, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
        learned_times_distribution: makeLearnedDistribution(),
      },
      loading: false,
      error: null,
    });

    renderModal();

    expect(screen.getByTestId("priority-bar-0")).toHaveAttribute("data-color", "#b91c1c");
    expect(screen.getByTestId("priority-bar-9")).toHaveAttribute("data-color", "#4ade80");
  });

  it("shows all bucket labels in the legend (including zero-count)", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([1, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        learned_times_distribution: makeLearnedDistribution(2, 0, 0, 0),
      },
      loading: false,
      error: null,
    });
    renderModal();
    const priorityLabels = [
      "Highest · 0",
      "Very high · 1",
      "High · 2",
      "Above average · 3",
      "Average · 4",
      "Below average · 5",
      "Low · 6",
      "Very low · 7",
      "Minimal · 8",
      "Default · 9",
    ];
    priorityLabels.forEach((label) =>
      expect(screen.getByText(label)).toBeInTheDocument()
    );
    // All 4 learned-times labels visible
    expect(screen.getByText("Never learned")).toBeInTheDocument();
    expect(screen.getByText("1–10 times")).toBeInTheDocument();
    expect(screen.getByText("11–30 times")).toBeInTheDocument();
    expect(screen.getByText("Over 30")).toBeInTheDocument();
  });

  it("shows section titles for learning and priority distributions", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([1]),
        learned_times_distribution: makeLearnedDistribution(1),
      },
      loading: false,
      error: null,
    });
    renderModal();
    expect(screen.getByText("Learning history")).toBeInTheDocument();
    expect(screen.getByText("Priority distribution")).toBeInTheDocument();
  });

  it("shows individual chart empty-state when only one distribution is all zeros", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([3]),       // has data
        learned_times_distribution: makeLearnedDistribution(0, 0, 0, 0), // empty
      },
      loading: false,
      error: null,
    });
    renderModal();
    // Global empty state should NOT show (priority has data)
    expect(screen.queryByText(/no vocabulary data yet/i)).not.toBeInTheDocument();
    // Per-chart empty state shown for learned-times
    expect(screen.getByText("No data yet")).toBeInTheDocument();
  });

  it("passes open=false to hook when modal is closed", () => {
    mockUseDistribution.mockReturnValue({ data: null, loading: false, error: null });
    renderModal(false);
    expect(mockUseDistribution).toHaveBeenCalledWith(false);
  });

  it("calls onClose when the statistics panel is clicked", () => {
    const onClose = vi.fn();
    mockUseDistribution.mockReturnValue({ data: null, loading: false, error: null });
    render(<VocabularyStatsModal open onClose={onClose} />);
    expect(
      screen.queryByRole("button", { name: "Close vocabulary statistics" })
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("dialog", { name: "Vocabulary statistics" })
    );
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    mockUseDistribution.mockReturnValue({ data: null, loading: false, error: null });
    render(<VocabularyStatsModal open onClose={onClose} />);

    const backdrop = document.querySelector(".MuiBackdrop-root");
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop as Element);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("dialog has accessible title", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([1]),
        learned_times_distribution: makeLearnedDistribution(1),
      },
      loading: false,
      error: null,
    });
    renderModal();
    expect(
      screen.getByRole("dialog", { name: /vocabulary statistics/i })
    ).toBeInTheDocument();
  });

  it("triggers a fresh fetch on each open (hook called with current open value)", async () => {
    mockUseDistribution.mockReturnValue({ data: null, loading: false, error: null });
    const { rerender } = render(
      <VocabularyStatsModal open={false} onClose={vi.fn()} />
    );
    expect(mockUseDistribution).toHaveBeenLastCalledWith(false);

    rerender(<VocabularyStatsModal open onClose={vi.fn()} />);
    await waitFor(() =>
      expect(mockUseDistribution).toHaveBeenLastCalledWith(true)
    );
  });
});
