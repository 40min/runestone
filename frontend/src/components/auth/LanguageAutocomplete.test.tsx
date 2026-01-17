import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LanguageAutocomplete from "./LanguageAutocomplete";
import { describe, it, expect, vi } from "vitest";

describe("LanguageAutocomplete", () => {
  it("renders with label", () => {
    render(
      <LanguageAutocomplete
        label="Mother Tongue"
        value=""
        onChange={() => {}}
      />
    );
    expect(screen.getByLabelText("Mother Tongue")).toBeInTheDocument();
  });

  it("calls onChange when an option is selected", async () => {
    const onChange = vi.fn();
    render(
      <LanguageAutocomplete
        label="Mother Tongue"
        value=""
        onChange={onChange}
      />
    );

    const input = screen.getByLabelText("Mother Tongue");
    await userEvent.type(input, "English");

    // MUI Autocomplete options are rendered in a portal, but vitest/jsdom should find it
    const option = await screen.findByText("English");
    fireEvent.click(option);

    expect(onChange).toHaveBeenCalledWith("English");
  });

  it("allows typing custom values (freeSolo)", async () => {
    const onChange = vi.fn();
    render(
      <LanguageAutocomplete
        label="Mother Tongue"
        value=""
        onChange={onChange}
      />
    );

    const input = screen.getByLabelText("Mother Tongue");
    await userEvent.type(input, "Klingon");

    expect(onChange).toHaveBeenCalledWith("Klingon");
  });

  it("displays the current value", () => {
    render(
      <LanguageAutocomplete
        label="Mother Tongue"
        value="Swedish"
        onChange={() => {}}
      />
    );
    const input = screen.getByLabelText("Mother Tongue") as HTMLInputElement;
    expect(input.value).toBe("Swedish");
  });
});
