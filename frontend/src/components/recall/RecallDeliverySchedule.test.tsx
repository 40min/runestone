import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RecallState } from "../../types/recall";
import RecallDeliverySchedule from "./RecallDeliverySchedule";

const configuredStopped: RecallState = {
  configured: true,
  delivery_enabled: false,
  recall_start_hour: 9,
  recall_end_hour: 22,
  timezone: "Europe/Helsinki",
  words: [],
};

const renderSchedule = (
  recall: RecallState = configuredStopped,
  overrides: Partial<React.ComponentProps<typeof RecallDeliverySchedule>> = {}
) => {
  const onSaveTimes = vi.fn();
  const onToggleDelivery = vi.fn();
  render(
    <RecallDeliverySchedule
      recall={recall}
      disabled={false}
      pendingAction={null}
      error={null}
      success={null}
      feedbackAction={null}
      onSaveTimes={onSaveTimes}
      onToggleDelivery={onToggleDelivery}
      {...overrides}
    />
  );
  return { onSaveTimes, onToggleDelivery };
};

const chooseHour = async (label: string, option: string) => {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: label }));
  await user.click(screen.getByRole("option", { name: option }));
};

describe("RecallDeliverySchedule", () => {
  it("sends both dirty hours with Start/Stop atomically", async () => {
    const user = userEvent.setup();
    const { onToggleDelivery } = renderSchedule();

    await chooseHour("Starts", "08:00");
    await chooseHour("Ends", "18:00");
    await user.click(screen.getByRole("button", { name: "Start delivery" }));

    expect(onToggleDelivery).toHaveBeenCalledWith(true, 8, 18);
  });

  it("shows equality feedback, focuses the schedule group, and blocks mutations", async () => {
    renderSchedule();
    await chooseHour("Ends", "09:00");

    expect(screen.getByRole("alert")).toHaveTextContent("must be different");
    expect(screen.getByRole("button", { name: "Save times" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start delivery" })).toBeDisabled();
    expect(screen.getByRole("group")).toHaveFocus();
  });

  it("disables schedule actions while a settings request is pending", () => {
    renderSchedule(configuredStopped, {
      pendingAction: { type: "saveSettings" },
    });

    expect(screen.getByRole("combobox", { name: "Starts" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(screen.getByRole("button", { name: "Save times" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start delivery" })).toBeDisabled();
  });

  it("keeps controls disabled for an absent or chat-less account", () => {
    renderSchedule({ ...configuredStopped, configured: false });

    expect(screen.getByRole("combobox", { name: "Starts" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(screen.getByRole("button", { name: "Start delivery" })).toBeDisabled();
  });

  it("exposes request failure feedback without changing the draft", async () => {
    const { rerender } = render(
      <RecallDeliverySchedule
        recall={configuredStopped}
        disabled={false}
        pendingAction={null}
        error={null}
        success={null}
        feedbackAction={null}
        onSaveTimes={vi.fn()}
        onToggleDelivery={vi.fn()}
      />
    );
    await chooseHour("Starts", "08:00");

    rerender(
      <RecallDeliverySchedule
        recall={configuredStopped}
        disabled={false}
        pendingAction={null}
        error="settings unavailable"
        success={null}
        feedbackAction="saveSettings"
        onSaveTimes={vi.fn()}
        onToggleDelivery={vi.fn()}
      />
    );

    expect(screen.getByRole("alert")).toHaveTextContent("settings unavailable");
    expect(screen.getByRole("combobox", { name: "Starts" })).toHaveTextContent(
      "08:00"
    );
  });
});
