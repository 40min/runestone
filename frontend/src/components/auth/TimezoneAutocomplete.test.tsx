import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import TimezoneAutocomplete, {
  getTimezoneOptions,
  isValidTimezone,
} from "./TimezoneAutocomplete";

describe("TimezoneAutocomplete", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds deduplicated options from supported, saved, and detected zones", () => {
    vi.spyOn(Intl, "supportedValuesOf").mockReturnValue([
      "Europe/Helsinki",
      "America/New_York",
      "Europe/Helsinki",
    ]);

    const options = getTimezoneOptions("Asia/Tokyo", "America/New_York");

    expect(options).toContain("UTC");
    expect(options).toContain("Asia/Tokyo");
    expect(options).toContain("America/New_York");
    expect(new Set(options).size).toBe(options.length);
  });

  it("keeps invalid saved values out and accepts only frozen valid identifiers", () => {
    expect(isValidTimezone("UTC")).toBe(true);
    expect(isValidTimezone("Europe/Helsinki")).toBe(true);
    expect(isValidTimezone("EST")).toBe(false);
    expect(isValidTimezone("not/a-zone")).toBe(false);
  });

  it("keeps UTC, saved, and detected values when supportedValuesOf is unavailable", () => {
    vi.spyOn(Intl, "supportedValuesOf").mockImplementation(() => {
      throw new TypeError("unsupported browser API");
    });

    expect(getTimezoneOptions("Europe/Helsinki", "America/New_York")).toEqual([
      "UTC",
      "America/New_York",
      "Europe/Helsinki",
    ]);
  });

  it("is searchable but does not commit free text", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <TimezoneAutocomplete
        label="Timezone"
        value="UTC"
        onChange={onChange}
      />
    );

    const input = screen.getByLabelText("Timezone");
    await user.type(input, "EST");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("emits a selected supported timezone", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <TimezoneAutocomplete
        label="Timezone"
        value="UTC"
        onChange={onChange}
      />
    );

    const input = screen.getByLabelText("Timezone");
    await user.click(input);
    await user.click(await screen.findByRole("option", { name: "Europe/Helsinki" }));

    expect(onChange).toHaveBeenCalledWith("Europe/Helsinki");
  });
});
