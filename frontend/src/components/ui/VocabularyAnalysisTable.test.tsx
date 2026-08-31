/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, beforeEach } from "vitest";
import VocabularyAnalysisTable from "./VocabularyAnalysisTable";
import type { EnrichedVocabularyItem } from "../../hooks/useImageProcessing";

const rows: EnrichedVocabularyItem[] = [
  {
    id: "hej",
    swedish: "hej",
    english: "hello",
    example_phrase: "Hej, hur mår du?",
    known: false,
  },
  {
    id: "bra",
    swedish: "bra",
    english: "good",
    example_phrase: undefined,
    known: true,
  },
];

const renderTable = (
  overrides: Partial<React.ComponentProps<typeof VocabularyAnalysisTable>> = {}
) => {
  const onSelectionChange = vi.fn();
  const onSelectAll = vi.fn();
  const props = {
    rows,
    selectedItems: new Map<string, boolean>(),
    onSelectionChange,
    onSelectAll,
    ...overrides,
  };
  render(<VocabularyAnalysisTable {...props} />);
  return { onSelectionChange, onSelectAll };
};

describe("VocabularyAnalysisTable", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a static table with the visible columns and one checkbox per row", () => {
    renderTable();

    expect(screen.getByRole("columnheader", { name: "Swedish" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "English" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Example Phrase" })).toBeInTheDocument();
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("Hej, hur mår du?")).toBeInTheDocument();
    expect(screen.getByText("bra")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();

    expect(document.getElementById("vocabulary-item-hej")).toBeInTheDocument();
    expect(document.getElementById("vocabulary-item-bra")).toBeInTheDocument();
  });

  it("forwards row checkbox changes with the row id", () => {
    const { onSelectionChange } = renderTable();

    fireEvent.click(document.getElementById("vocabulary-item-hej")!);

    expect(onSelectionChange).toHaveBeenCalledWith("hej", true);
  });

  it("checks and unchecks all rows through the master checkbox", () => {
    const selectedItems = new Map<string, boolean>([
      ["hej", true],
      ["bra", true],
    ]);
    const { onSelectAll } = renderTable({ selectedItems });

    const master = document.getElementById("vocabulary-master-checkbox")!;
    expect(master).toBeChecked();

    fireEvent.click(master);
    expect(onSelectAll).toHaveBeenCalledWith(false);
  });

  it("renders selectable mobile cards when the viewport is small", () => {
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("max-width"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    try {
      const { onSelectionChange, onSelectAll } = renderTable();

      expect(screen.queryByRole("table")).not.toBeInTheDocument();
      expect(screen.getByText("Select All")).toBeInTheDocument();
      expect(screen.getByText("hej")).toBeInTheDocument();
      expect(screen.getByText("Hej, hur mår du?")).toBeInTheDocument();
      expect(document.getElementById("vocabulary-item-hej")).toBeInTheDocument();

      fireEvent.click(document.getElementById("vocabulary-item-bra")!);
      expect(onSelectionChange).toHaveBeenCalledWith("bra", true);

      fireEvent.click(document.getElementById("vocabulary-master-checkbox")!);
      expect(onSelectAll).toHaveBeenCalledWith(true);
    } finally {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: originalMatchMedia,
      });
    }
  });
});
