import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RecallView from "./RecallView";

const mockUseRecall = vi.hoisted(() => vi.fn());

vi.mock("../hooks/useRecall", () => ({
  useRecall: mockUseRecall,
}));

const refreshSelection = vi.fn().mockResolvedValue(undefined);
const postponeWord = vi.fn().mockResolvedValue(undefined);
const removeWord = vi.fn().mockResolvedValue(undefined);
const refetch = vi.fn().mockResolvedValue(undefined);
const clearFeedback = vi.fn();

const populatedRecall = {
  configured: true,
  delivery_enabled: true,
  words: [
    {
      id: 42,
      word_phrase: "kontanter",
      translation: "cash",
      example_phrase: "Jag betalar med kontanter.",
    },
    {
      id: 43,
      word_phrase: "lagom",
    },
  ],
};

const setHookState = (overrides: Record<string, unknown> = {}) => {
  mockUseRecall.mockReturnValue({
    recall: populatedRecall,
    loading: false,
    pendingAction: null,
    error: null,
    success: null,
    refetch,
    refreshSelection,
    postponeWord,
    removeWord,
    clearFeedback,
    ...overrides,
  });
};

describe("RecallView", () => {
  beforeEach(() => {
    setHookState();
  });

  it("renders loading and initial error states with a retry action", async () => {
    const user = userEvent.setup();
    setHookState({ recall: null, loading: true });
    const { rerender } = render(<RecallView />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText("Loading recall selection…")).toBeInTheDocument();

    setHookState({
      recall: null,
      loading: false,
      error: "Recall request failed",
    });
    rerender(<RecallView />);

    expect(screen.getByText("Recall request failed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(refetch).toHaveBeenCalledOnce();
  });

  it("renders the unconfigured onboarding state", () => {
    setHookState({
      recall: {
        configured: false,
        delivery_enabled: false,
        words: [],
      },
    });

    render(<RecallView />);

    expect(screen.getByText("Recall is not configured")).toBeInTheDocument();
    expect(
      screen.getByText(/Link your Telegram username in Profile/)
    ).toBeInTheDocument();
    expect(screen.getByText("/start")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh selection" })
    ).toBeDisabled();
  });

  it("renders the configured empty state and leaves refresh available", () => {
    setHookState({
      recall: {
        configured: true,
        delivery_enabled: false,
        words: [],
      },
    });

    render(<RecallView />);

    expect(screen.getByText("No words selected")).toBeInTheDocument();
    expect(
      screen.getByText(
        "There are currently no eligible vocabulary words for recall."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Delivery disabled")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh selection" })
    ).toBeEnabled();
  });

  it("keeps queue management available while delivery is disabled", () => {
    setHookState({
      recall: {
        ...populatedRecall,
        delivery_enabled: false,
      },
    });

    render(<RecallView />);

    expect(screen.getByText("Delivery disabled")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh selection" })
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Postpone kontanter" })
    ).toBeEnabled();
    expect(
      screen.getByRole("button", {
        name: "Remove kontanter from learning",
      })
    ).toBeEnabled();
  });

  it("renders an ordered queue with optional word details", () => {
    render(<RecallView />);

    expect(
      screen.getByRole("heading", {
        name: "Recall Your Swedish Vocabulary",
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("complementary", {
        name: "Recall session summary",
      })
    ).toBeInTheDocument();
    expect(screen.getByText("Changes sync with Telegram.")).toBeInTheDocument();
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("kontanter")).toBeInTheDocument();
    expect(screen.getByText("cash")).toBeInTheDocument();
    expect(
      screen.getByText("Jag betalar med kontanter.")
    ).toBeInTheDocument();
    expect(screen.getByText("lagom")).toBeInTheDocument();
  });

  it("uses a prominent refresh action and compact row actions with the agreed tooltips", async () => {
    const user = userEvent.setup();
    render(<RecallView />);

    const refresh = screen.getByRole("button", {
      name: "Refresh selection",
    });
    const postpone = screen.getByRole("button", {
      name: "Postpone kontanter",
    });
    const remove = screen.getByRole("button", {
      name: "Remove kontanter from learning",
    });

    expect(refresh).toHaveTextContent("Refresh selection");
    expect(postpone).toHaveTextContent("");
    expect(remove).toHaveTextContent("");

    await user.hover(refresh);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Refresh selection: lowers the priority of all current words and replaces the selection."
    );
    await user.unhover(refresh);

    await user.hover(postpone);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Postpone: moves this word out of the current selection and lowers its recall priority."
    );
    await user.unhover(postpone);

    await user.hover(remove);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Remove from learning: stops learning this word and removes it from the current selection."
    );
  });

  it("exposes every action tooltip to keyboard focus", async () => {
    const user = userEvent.setup();
    render(<RecallView />);

    const actions = [
      {
        button: screen.getByRole("button", {
          name: "Refresh selection",
        }),
        tooltip:
          "Refresh selection: lowers the priority of all current words and replaces the selection.",
      },
      {
        button: screen.getByRole("button", {
          name: "Postpone kontanter",
        }),
        tooltip:
          "Postpone: moves this word out of the current selection and lowers its recall priority.",
      },
      {
        button: screen.getByRole("button", {
          name: "Remove kontanter from learning",
        }),
        tooltip:
          "Remove from learning: stops learning this word and removes it from the current selection.",
      },
    ];

    for (const action of actions) {
      await user.tab();
      expect(action.button).toHaveFocus();
      expect(
        await screen.findByRole("tooltip", { name: action.tooltip })
      ).toBeVisible();
    }
  });

  it("dispatches refresh, postpone, and remove without confirmation", async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm");
    render(<RecallView />);

    await user.click(
      screen.getByRole("button", { name: "Refresh selection" })
    );
    await user.click(
      screen.getByRole("button", { name: "Postpone kontanter" })
    );
    await user.click(
      screen.getByRole("button", {
        name: "Remove kontanter from learning",
      })
    );

    expect(refreshSelection).toHaveBeenCalledOnce();
    expect(postponeWord).toHaveBeenCalledWith(42, "kontanter");
    expect(removeWord).toHaveBeenCalledWith(42, "kontanter");
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("shows row-level progress and disables conflicting actions", () => {
    setHookState({
      pendingAction: { type: "postpone", vocabularyId: 42 },
    });

    render(<RecallView />);

    expect(
      screen.getByRole("button", { name: "Postpone kontanter" })
    ).toContainElement(screen.getByRole("progressbar"));
    for (const button of screen.getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });

  it("renders mutation feedback", () => {
    setHookState({
      success: "Recall selection refreshed.",
      error: "Could not postpone word",
    });

    render(<RecallView />);

    expect(screen.getByText("Recall selection refreshed.")).toBeInTheDocument();
    expect(screen.getByText("Could not postpone word")).toBeInTheDocument();
  });
});
