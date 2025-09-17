/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { vi } from 'vitest';
import SearchInput from "./SearchInput";

describe("SearchInput", () => {
  it("renders with default placeholder", () => {
    render(<SearchInput value="" onChange={vi.fn()} />);

    const input = screen.getByPlaceholderText("Search...");
    expect(input).toBeInTheDocument();
  });

  it("renders with custom placeholder", () => {
    const customPlaceholder = "Search vocabulary...";
    render(<SearchInput value="" onChange={vi.fn()} placeholder={customPlaceholder} />);

    const input = screen.getByPlaceholderText(customPlaceholder);
    expect(input).toBeInTheDocument();
  });

  it("displays the provided value", () => {
    const testValue = "test search";
    render(<SearchInput value={testValue} onChange={vi.fn()} />);

    const input = screen.getByDisplayValue(testValue);
    expect(input).toBeInTheDocument();
  });

  it("calls onChange when input value changes", () => {
    const mockOnChange = vi.fn();

    render(<SearchInput value="" onChange={mockOnChange} />);

    const input = screen.getByPlaceholderText("Search...");
    fireEvent.change(input, { target: { value: "test" } });

    expect(mockOnChange).toHaveBeenCalledTimes(1);
  });

  it("applies custom sx styles", () => {
    const customSx = { marginTop: 2 };
    render(<SearchInput value="" onChange={vi.fn()} sx={customSx} />);

    // The component should render without errors with custom sx
    const input = screen.getByPlaceholderText("Search...");
    expect(input).toBeInTheDocument();
  });

  it("renders search button when onSearch is provided", () => {
    render(<SearchInput value="" onChange={vi.fn()} onSearch={vi.fn()} />);

    const button = screen.getByRole("button", { name: /search/i });
    expect(button).toBeInTheDocument();
  });

  it("does not render search button when onSearch is not provided", () => {
    render(<SearchInput value="" onChange={vi.fn()} />);

    const button = screen.queryByRole("button", { name: /search/i });
    expect(button).not.toBeInTheDocument();
  });

  it("calls onSearch when search button is clicked", () => {
    const mockOnSearch = vi.fn();
    render(<SearchInput value="" onChange={vi.fn()} onSearch={mockOnSearch} />);

    const button = screen.getByRole("button", { name: /search/i });
    fireEvent.click(button);

    expect(mockOnSearch).toHaveBeenCalledTimes(1);
  });
});