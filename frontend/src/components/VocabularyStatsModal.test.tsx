/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import VocabularyStatsModal from "./VocabularyStatsModal";

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

// Recharts is SVG-heavy and doesn't render well in jsdom — stub it so tests
// can focus on accessible text and labels without relying on SVG internals.
vi.mock("recharts", () => ({
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: ({ data, nameKey, children }: { data: Array<Record<string, unknown>>; nameKey: string; children: React.ReactNode }) => (
    <ul data-testid="pie-slices">
      {data.map((entry) => (
        <li key={String(entry[nameKey])} data-testid="pie-slice">
          {String(entry[nameKey])}: {String(entry["count"])}
        </li>
      ))}
      {children}
    </ul>
  ),
  Cell: ({ fill }: { fill: string }) => <li data-testid="pie-cell" data-fill={fill} />,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
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

  it("shows loading spinner while fetching", () => {
    mockUseDistribution.mockReturnValue({ data: null, loading: true, error: null });
    renderModal();
    // LoadingSpinner renders a CircularProgress; check it's present
    expect(document.querySelector("[role='progressbar']")).toBeInTheDocument();
    expect(screen.queryByTestId("pie-chart")).not.toBeInTheDocument();
  });

  it("shows loading spinner before the initial request updates loading state", () => {
    mockUseDistribution.mockReturnValue({
      data: null,
      loading: false,
      error: null,
    });
    renderModal();
    expect(document.querySelector("[role='progressbar']")).toBeInTheDocument();
    expect(screen.queryByTestId("pie-chart")).not.toBeInTheDocument();
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
    expect(screen.queryByTestId("pie-chart")).not.toBeInTheDocument();
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
    expect(screen.queryByTestId("pie-chart")).not.toBeInTheDocument();
  });

  it("renders charts section when data has positive counts", () => {
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
    // Two pie charts rendered
    const charts = screen.getAllByTestId("pie-chart");
    expect(charts.length).toBe(2);
  });

  it("renders only positive-count slices in the pie", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([5, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        learned_times_distribution: makeLearnedDistribution(3, 0, 0, 0),
      },
      loading: false,
      error: null,
    });
    renderModal();
    // Our Pie stub renders only positive-count entries
    const slices = screen.getAllByTestId("pie-slice");
    // Priority pie: only count=5 slice; Learned pie: only count=3 slice
    expect(slices).toHaveLength(2);
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

    const cells = screen.getAllByTestId("pie-cell");
    expect(cells[0]).toHaveAttribute("data-fill", "#991b1b");
    expect(cells[1]).toHaveAttribute("data-fill", "#4ade80");
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
    // All 10 priority labels visible
    for (let i = 0; i < 10; i++) {
      expect(screen.getByText(`Priority ${i}`)).toBeInTheDocument();
    }
    // All 4 learned-times labels visible
    expect(screen.getByText("Never")).toBeInTheDocument();
    expect(screen.getByText("1\u201310")).toBeInTheDocument();
    expect(screen.getByText("11\u201330")).toBeInTheDocument();
    expect(screen.getByText(">30")).toBeInTheDocument();
  });

  it("shows section titles for both charts", () => {
    mockUseDistribution.mockReturnValue({
      data: {
        priority_distribution: makePriorityDistribution([1]),
        learned_times_distribution: makeLearnedDistribution(1),
      },
      loading: false,
      error: null,
    });
    renderModal();
    expect(screen.getByText("Words by Priority")).toBeInTheDocument();
    expect(screen.getByText("Words by Times Learned")).toBeInTheDocument();
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

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    mockUseDistribution.mockReturnValue({ data: null, loading: false, error: null });
    render(<VocabularyStatsModal open onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Close vocabulary statistics" }));
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
