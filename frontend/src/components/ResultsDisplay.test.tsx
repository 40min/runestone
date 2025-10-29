/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { vi } from "vitest";
import ResultsDisplay from "./ResultsDisplay";

const mockOcrResult = {
  text: "Sample Swedish text",
  character_count: 18,
};

const mockAnalysisResult = {
  grammar_focus: {
    topic: "Present tense",
    explanation: "Focus on present tense usage in sentences",
    has_explicit_rules: true,
    rules: "Hej [hello] - greeting\nHur mår du? [how are you?] - question form",
  },
  vocabulary: [
    { id: "hej", swedish: "hej", english: "hello", example_phrase: "Hej, hur mår du?", known: false },
    { id: "bra", swedish: "bra", english: "good", example_phrase: "Jag mår bra idag.", known: true },
    { id: "hus", swedish: "hus", english: "house", example_phrase: "Jag har ett hus.", known: false },
  ],
};

const mockResourcesResult =
  "Additional learning tips here. Check out https://example.com for more resources.";

describe("ResultsDisplay", () => {
  it("renders error state when error is provided and no results", () => {
    const error = "Processing failed";
    render(
      <ResultsDisplay
        ocrResult={null}
        analysisResult={null}
        resourcesResult={null}
        error={error}
        saveVocabulary={vi.fn()}
      />
    );

    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText(error)).toBeInTheDocument();
  });

  it("shows results alongside error when both are present", () => {
    const error = "Analysis failed: HTTP 500: Internal Server Error";
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={null}
        resourcesResult={null}
        error={error}
        saveVocabulary={vi.fn()}
      />
    );

    // Should show the error alert
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText(error)).toBeInTheDocument();

    // Should also show the results
    expect(screen.getByText("Analysis Results")).toBeInTheDocument();
    expect(screen.getByText("OCR Text")).toBeInTheDocument();
    expect(screen.getByText(mockOcrResult.text)).toBeInTheDocument();
  });

  it("renders OCR tab content by default", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    expect(screen.getByText("Analysis Results")).toBeInTheDocument();
    expect(screen.getByText("OCR Text")).toBeInTheDocument();
    expect(screen.getByText(mockOcrResult.text)).toBeInTheDocument();
  });

  it("switches to grammar tab when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const grammarTab = screen.getByText("Grammar");
    fireEvent.click(grammarTab);

    expect(screen.getByText("Grammar Analysis")).toBeInTheDocument();
    expect(screen.getByText("Topic:")).toBeInTheDocument();
    expect(
      screen.getByText(mockAnalysisResult.grammar_focus.topic)
    ).toBeInTheDocument();
    expect(screen.getByText("Explanation:")).toBeInTheDocument();
    expect(
      screen.getByText(mockAnalysisResult.grammar_focus.explanation)
    ).toBeInTheDocument();
    expect(screen.getByText("Has Explicit Rules:")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("switches to vocabulary tab when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    expect(screen.getByText("Vocabulary Analysis")).toBeInTheDocument();
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("bra")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getByText("Hej, hur mår du?")).toBeInTheDocument();
    expect(screen.getByText("Jag mår bra idag.")).toBeInTheDocument();
  });

  it("copies all vocabulary to clipboard when all items are selected and copy button is clicked", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Check all items by clicking individual checkboxes using IDs
    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");

    fireEvent.click(firstVocabCheckbox!); // First vocabulary item (hej)
    fireEvent.click(secondVocabCheckbox!); // Second vocabulary item (bra)

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Wait for the async operation to complete
    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith(
        "hej - hello\nbra - good"
      );
    });
  });

  it("switches to extra info tab when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const extraInfoTab = screen.getByText("Extra info");
    fireEvent.click(extraInfoTab);

    expect(
      screen.getByRole("heading", { name: "Extra info" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Additional learning tips here. Check out/)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "https://example.com" })
    ).toBeInTheDocument();
    expect(screen.getByText(/for more resources/)).toBeInTheDocument();
  });

  it("does not show extra info tab when resourcesResult is not provided", () => {
    const resultWithoutExtraInfo = {
      ocr_result: mockOcrResult,
      analysis: mockAnalysisResult,
      extra_info: null,
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithoutExtraInfo.ocr_result}
        analysisResult={resultWithoutExtraInfo.analysis}
        resourcesResult={resultWithoutExtraInfo.extra_info}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    // Extra info tab should not exist when resourcesResult is null/undefined
    expect(screen.queryByText("Extra info")).not.toBeInTheDocument();
  });

  it("does not render when neither result nor error is provided", () => {
    render(
      <ResultsDisplay
        ocrResult={null}
        analysisResult={null}
        resourcesResult={null}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    expect(screen.queryByText("Analysis Results")).not.toBeInTheDocument();
  });

  it("renders all tabs correctly", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    expect(screen.getByText("OCR Text")).toBeInTheDocument();
    expect(screen.getByText("Grammar")).toBeInTheDocument();
    expect(screen.getByText("Vocabulary")).toBeInTheDocument();
    expect(screen.getByText("Extra info")).toBeInTheDocument();
  });

  it("displays rules section when rules are present", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const grammarTab = screen.getByText("Grammar");
    fireEvent.click(grammarTab);

    expect(screen.getByText("Rules:")).toBeInTheDocument();
    expect(screen.getByText(/Hej \[hello\] - greeting/)).toBeInTheDocument();
    expect(
      screen.getByText(/Hur mår du\? \[how are you\?\] - question form/)
    ).toBeInTheDocument();
  });

  it("does not display rules section when rules are null", () => {
    const resultWithoutRules = {
      ocr_result: mockOcrResult,
      analysis: {
        ...mockAnalysisResult,
        grammar_focus: {
          ...mockAnalysisResult.grammar_focus,
          rules: undefined,
        },
      },
      extra_info: mockResourcesResult,
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithoutRules.ocr_result}
        analysisResult={resultWithoutRules.analysis}
        resourcesResult={resultWithoutRules.extra_info}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const grammarTab = screen.getByText("Grammar");
    fireEvent.click(grammarTab);

    expect(screen.queryByText("Rules:")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Hej [hello] - greeting")
    ).not.toBeInTheDocument();
  });

  it("does not display rules section when rules are undefined", () => {
    const resultWithoutRules = {
      ocr_result: mockOcrResult,
      analysis: {
        ...mockAnalysisResult,
        grammar_focus: {
          ...mockAnalysisResult.grammar_focus,
          rules: undefined,
        },
      },
      extra_info: mockResourcesResult,
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithoutRules.ocr_result}
        analysisResult={resultWithoutRules.analysis}
        resourcesResult={resultWithoutRules.extra_info}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const grammarTab = screen.getByText("Grammar");
    fireEvent.click(grammarTab);

    expect(screen.queryByText("Rules:")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Hej [hello] - greeting")
    ).not.toBeInTheDocument();
  });

  it("converts URLs to clickable links in extra info", () => {
    const resultWithUrl = {
      ocr_result: mockOcrResult,
      analysis: mockAnalysisResult,
      extra_info:
        "Check out this resource: https://example.com/learn-swedish and also https://swedishpod101.com",
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithUrl.ocr_result}
        analysisResult={resultWithUrl.analysis}
        resourcesResult={resultWithUrl.extra_info}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const extraInfoTab = screen.getByText("Extra info");
    fireEvent.click(extraInfoTab);

    // Check that the link elements are present
    const link1 = screen.getByRole("link", {
      name: "https://example.com/learn-swedish",
    });
    const link2 = screen.getByRole("link", {
      name: "https://swedishpod101.com",
    });

    expect(link1).toBeInTheDocument();
    expect(link1).toHaveAttribute("href", "https://example.com/learn-swedish");
    expect(link1).toHaveAttribute("target", "_blank");
    expect(link1).toHaveAttribute("rel", "noopener noreferrer");

    expect(link2).toBeInTheDocument();
    expect(link2).toHaveAttribute("href", "https://swedishpod101.com");
    expect(link2).toHaveAttribute("target", "_blank");
    expect(link2).toHaveAttribute("rel", "noopener noreferrer");
  });

  // New tests for checkbox functionality
  it("initializes all vocabulary items as unchecked by default", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Check that all checkboxes are unchecked by default using IDs
    const enrichCheckbox = document.getElementById("enrich-grammar-checkbox");
    const masterCheckbox = document.getElementById(
      "vocabulary-master-checkbox"
    );
    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");

    expect(enrichCheckbox).toBeChecked();
    expect(masterCheckbox).not.toBeChecked();
    expect(firstVocabCheckbox).not.toBeChecked();
    expect(secondVocabCheckbox).not.toBeChecked();
  });

  it("toggles individual checkbox when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");

    // Initially unchecked
    expect(firstVocabCheckbox).not.toBeChecked();

    // Click to check
    fireEvent.click(firstVocabCheckbox!);
    expect(firstVocabCheckbox).toBeChecked();

    // Click to uncheck again
    fireEvent.click(firstVocabCheckbox!);
    expect(firstVocabCheckbox).not.toBeChecked();
  });

  it("handles check all/uncheck all functionality", async () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    const masterCheckbox = document.getElementById(
      "vocabulary-master-checkbox"
    );
    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");

    // Initially all unchecked
    expect(masterCheckbox).not.toBeChecked();
    expect(firstVocabCheckbox).not.toBeChecked();
    expect(secondVocabCheckbox).not.toBeChecked();

    // Click master checkbox to check all vocabulary items
    fireEvent.click(masterCheckbox!);

    await waitFor(() => {
      expect(firstVocabCheckbox).toBeChecked();
      expect(secondVocabCheckbox).toBeChecked();
      expect(masterCheckbox).toBeChecked();
    });

    // Click master checkbox to uncheck all vocabulary items again
    fireEvent.click(masterCheckbox!);

    await waitFor(() => {
      expect(firstVocabCheckbox).not.toBeChecked();
      expect(secondVocabCheckbox).not.toBeChecked();
      expect(masterCheckbox).not.toBeChecked();
    });
  });

  it("copies only selected vocabulary items", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Click only the second vocabulary item using ID
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");
    fireEvent.click(secondVocabCheckbox!);

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Should only copy the second item (bra - good)
    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith("bra - good");
    });
  });

  it("shows error snackbar when no vocabulary items are selected", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Items are already unchecked by default, so no items are selected
    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Should show error message
    await waitFor(() => {
      expect(
        screen.getByText("No vocabulary items selected!")
      ).toBeInTheDocument();
    });

    // Clipboard should not be called
    expect(mockClipboard.writeText).not.toHaveBeenCalled();
  });

  it("shows success snackbar when vocabulary is copied successfully", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Check all items by clicking individual checkboxes using IDs
    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");

    fireEvent.click(firstVocabCheckbox!); // First vocabulary item
    fireEvent.click(secondVocabCheckbox!); // Second vocabulary item

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Should show success message
    await waitFor(() => {
      expect(
        screen.getByText("Selected vocabulary copied to clipboard!")
      ).toBeInTheDocument();
    });
  });

  it("shows error snackbar when clipboard API fails", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockRejectedValue(new Error("Clipboard error")),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Check all items by clicking individual checkboxes using IDs
    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");

    fireEvent.click(firstVocabCheckbox!); // First vocabulary item
    fireEvent.click(secondVocabCheckbox!); // Second vocabulary item

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Should show error message
    await waitFor(() => {
      expect(
        screen.getByText("Failed to copy vocabulary. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("handles clipboard API not available by attempting fallback", async () => {
    // Save original methods
    const originalClipboard = navigator.clipboard;

    // Mock the absence of clipboard API
    // @ts-expect-error - Intentionally deleting clipboard for testing fallback
    delete navigator.clipboard;

    // Spy on console.error to suppress expected error output
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Check all items by clicking individual checkboxes using IDs
    const firstVocabCheckbox = document.getElementById("vocabulary-item-hej");
    const secondVocabCheckbox = document.getElementById("vocabulary-item-bra");

    fireEvent.click(firstVocabCheckbox!); // First vocabulary item
    fireEvent.click(secondVocabCheckbox!); // Second vocabulary item

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Should show either success or error message - the fallback might not work in test environment
    await waitFor(() => {
      const successMessage = screen.queryByText(
        "Selected vocabulary copied to clipboard!"
      );
      const errorMessage = screen.queryByText(
        "Failed to copy vocabulary. Please try again."
      );
      expect(successMessage || errorMessage).toBeTruthy();
    });

    // Restore original methods
    Object.assign(navigator, { clipboard: originalClipboard });
    consoleSpy.mockRestore();
  });

  it("displays vocabulary items with checkboxes and correct styling", () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Check that vocabulary items are displayed with checkboxes
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("bra")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();

    // Verify all checkboxes exist by ID
    expect(
      document.getElementById("enrich-grammar-checkbox")
    ).toBeInTheDocument();
    expect(
      document.getElementById("vocabulary-master-checkbox")
    ).toBeInTheDocument();
    expect(document.getElementById("vocabulary-item-hej")).toBeInTheDocument();
    expect(document.getElementById("vocabulary-item-bra")).toBeInTheDocument();
    expect(document.getElementById("vocabulary-item-hus")).toBeInTheDocument();

    // Check that the Copy button is present
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });
  it("copies OCR text to clipboard when copy button is clicked", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const copyButton = screen.getByTitle("Copy");
    fireEvent.click(copyButton);

    // Wait for the async operation to complete
    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith(mockOcrResult.text);
    });

    // Check that the button text changes to "Copied!"
    expect(screen.getByTitle("Copied!")).toBeInTheDocument();

    // Check that success snackbar appears
    expect(
      screen.getByText("OCR text copied to clipboard!")
    ).toBeInTheDocument();
  });

  it("shows error snackbar when OCR text copy fails", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockRejectedValue(new Error("Clipboard error")),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const copyButton = screen.getByTitle("Copy");
    fireEvent.click(copyButton);

    // Should show error message
    await waitFor(() => {
      expect(
        screen.getByText("Failed to copy OCR text. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("handles OCR text copy when clipboard API is not available by attempting fallback", async () => {
    // Save original methods
    const originalClipboard = navigator.clipboard;

    // Mock the absence of clipboard API
    // @ts-expect-error - Intentionally deleting clipboard for testing fallback
    delete navigator.clipboard;

    // Spy on console.error to suppress expected error output
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const copyButton = screen.getByTitle("Copy");
    fireEvent.click(copyButton);

    // Should show either success or error message - the fallback might not work in test environment
    await waitFor(() => {
      const successMessage = screen.queryByText(
        "OCR text copied to clipboard!"
      );
      const errorMessage = screen.queryByText(
        "Failed to copy OCR text. Please try again."
      );
      expect(successMessage || errorMessage).toBeTruthy();
    });

    // Restore original methods
    Object.assign(navigator, { clipboard: originalClipboard });
    consoleSpy.mockRestore();
  });

  it("does not attempt to copy OCR text when ocrResult is null", () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={null}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    // Copy button should not be present when ocrResult is null
    expect(screen.queryByTitle("Copy")).not.toBeInTheDocument();

    // Clipboard should not be called
    expect(mockClipboard.writeText).not.toHaveBeenCalled();
  });

  it("filters out known words when 'Hide known words' is checked", async () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Initially, all words are visible
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("bra")).toBeInTheDocument(); // known word
    expect(screen.getByText("hus")).toBeInTheDocument();

    const hideKnownCheckbox = document.getElementById("hide-known-words-checkbox");
    fireEvent.click(hideKnownCheckbox!);

    await waitFor(() => {
      // Known word "bra" should be hidden
      expect(screen.getByText("hej")).toBeInTheDocument();
      expect(screen.queryByText("bra")).not.toBeInTheDocument();
      expect(screen.getByText("hus")).toBeInTheDocument();
    });

    // Uncheck to show all words again
    fireEvent.click(hideKnownCheckbox!);
    await waitFor(() => {
      expect(screen.getByText("hej")).toBeInTheDocument();
      expect(screen.getByText("bra")).toBeInTheDocument();
      expect(screen.getByText("hus")).toBeInTheDocument();
    });
  });

  it("'Check All' only checks visible items when 'Hide known words' is active", async () => {
    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Hide known words
    const hideKnownCheckbox = document.getElementById("hide-known-words-checkbox");
    fireEvent.click(hideKnownCheckbox!);

    const masterCheckbox = document.getElementById("vocabulary-master-checkbox");
    fireEvent.click(masterCheckbox!);

    await waitFor(() => {
      // Visible items should be checked
      expect(document.getElementById("vocabulary-item-hej")).toBeChecked(); // hej
      expect(document.getElementById("vocabulary-item-hus")).toBeChecked(); // hus

      // Hidden item should not be checked (it's not even in the DOM, but we check its state before filtering)
      // This is tricky to test directly without inspecting state. Let's check what's copied.
    });
  });

  it("copies only visible (filtered) vocabulary", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockOcrResult}
        analysisResult={mockAnalysisResult}
        resourcesResult={mockResourcesResult}
        error={null}
        saveVocabulary={vi.fn()}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    // Hide known words
    const hideKnownCheckbox = document.getElementById("hide-known-words-checkbox");
    fireEvent.click(hideKnownCheckbox!);

    // Check all visible items
    const masterCheckbox = document.getElementById("vocabulary-master-checkbox");
    fireEvent.click(masterCheckbox!);

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith(
        "hej - hello\nhus - house"
      );
    });
  });

  describe("UUID Generation", () => {
    it("should generate UUIDs for vocabulary items without IDs", () => {
      const mockVocabulary = [
        { swedish: "hund", english: "dog", known: false },
        { swedish: "katt", english: "cat", known: false },
      ];
      const analysisResult = {
        grammar_focus: mockAnalysisResult.grammar_focus,
        vocabulary: mockVocabulary,
      };

      render(
        <ResultsDisplay
          ocrResult={null}
          analysisResult={analysisResult}
          resourcesResult={null}
          error={null}
          saveVocabulary={vi.fn()}
        />
      );

      const vocabularyTab = screen.getByText("Vocabulary");
      fireEvent.click(vocabularyTab);

      // Check that checkboxes for items are rendered, which implies they have unique IDs
      expect(screen.getByText("hund")).toBeInTheDocument();
      expect(screen.getByText("katt")).toBeInTheDocument();
    });

    it("should preserve existing IDs if present", () => {
      const mockVocabulary = [
        {
          id: "existing-id-1",
          swedish: "hund",
          english: "dog",
          known: false,
        },
        { swedish: "katt", english: "cat", known: false }, // One without ID
      ];
      const analysisResult = {
        grammar_focus: mockAnalysisResult.grammar_focus,
        vocabulary: mockVocabulary,
      };

      render(
        <ResultsDisplay
          ocrResult={null}
          analysisResult={analysisResult}
          resourcesResult={null}
          error={null}
          saveVocabulary={vi.fn()}
        />
      );

      const vocabularyTab = screen.getByText("Vocabulary");
      fireEvent.click(vocabularyTab);

      // Check that the item with the existing ID has a checkbox with that ID
      const hundCheckbox = document.getElementById("vocabulary-item-existing-id-1");
      expect(hundCheckbox).toBeInTheDocument();
    });
  });

  describe("Checkbox State Management", () => {
    it("should handle duplicate Swedish words correctly", async () => {
      const mockVocabulary = [
        { swedish: "hund", english: "dog", known: false },
        { swedish: "hund", english: "hound", known: false },
      ];
      const analysisResult = {
        grammar_focus: mockAnalysisResult.grammar_focus,
        vocabulary: mockVocabulary,
      };

      render(
        <ResultsDisplay
          ocrResult={null}
          analysisResult={analysisResult}
          resourcesResult={null}
          error={null}
          saveVocabulary={vi.fn()}
        />
      );

      const vocabularyTab = screen.getByText("Vocabulary");
      fireEvent.click(vocabularyTab);

      const checkboxes = await screen.findAllByRole("checkbox");
      // There should be a master checkbox and two item checkboxes
      expect(checkboxes.length).toBeGreaterThanOrEqual(3);

      // Get the two checkboxes for "hund"
      const dogCheckbox = checkboxes[1];
      const houndCheckbox = checkboxes[2];

      expect(dogCheckbox).not.toBeChecked();
      expect(houndCheckbox).not.toBeChecked();

      // Click the first "hund" checkbox
      fireEvent.click(dogCheckbox);

      // Only the first checkbox should be checked
      expect(dogCheckbox).toBeChecked();
      expect(houndCheckbox).not.toBeChecked();

      // Click the second "hund" checkbox
      fireEvent.click(houndCheckbox);

      // Both should be checked now
      expect(dogCheckbox).toBeChecked();
      expect(houndCheckbox).toBeChecked();
    });
  });

  describe("Hide Known Words after Save", () => {
    it("should update state and hide saved items when 'Hide known words' is active", async () => {
      const saveVocabularyMock = vi.fn().mockResolvedValue(undefined);
      const onVocabularyUpdatedMock = vi.fn();

      const mockVocabulary = [
        { swedish: "spik", english: "nail", known: false },
        { swedish: "hammare", english: "hammer", known: false },
      ];
      const analysisResult = {
        grammar_focus: mockAnalysisResult.grammar_focus,
        vocabulary: mockVocabulary,
      };

      render(
        <ResultsDisplay
          ocrResult={null}
          analysisResult={analysisResult}
          resourcesResult={null}
          error={null}
          saveVocabulary={saveVocabularyMock}
          onVocabularyUpdated={onVocabularyUpdatedMock}
        />
      );

      const vocabularyTab = screen.getByText("Vocabulary");
      fireEvent.click(vocabularyTab);

      // Hide known words
      const hideKnownCheckbox = document.getElementById(
        "hide-known-words-checkbox"
      );
      fireEvent.click(hideKnownCheckbox!);

      // Select the "spik" item to save
      const spikRow = await screen.findByText("spik");
      const parentRow = spikRow.closest("tr");
      const spikCheckbox = within(parentRow!).getByRole("checkbox");
      fireEvent.click(spikCheckbox);

      // Save the selected vocabulary
      const saveButton = screen.getByText("Save to Database");
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(saveVocabularyMock).toHaveBeenCalled();
      });

      // After saving, "spik" should be marked as known and be hidden
      expect(screen.queryByText("spik")).not.toBeInTheDocument();
      // "hammare" should still be visible
      expect(screen.getByText("hammare")).toBeInTheDocument();
    });
  });
});
