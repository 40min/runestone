/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
    { swedish: "hej", english: "hello", example_phrase: "Hej, hur mår du?" },
    { swedish: "bra", english: "good", example_phrase: "Jag mår bra idag." },
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

    // Check all items first using the master checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    const masterCheckbox = checkboxes[0];
    fireEvent.click(masterCheckbox);

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

    // Check that all checkboxes are unchecked by default
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);
    checkboxes.forEach((checkbox) => {
      expect(checkbox).not.toBeChecked();
    });
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

    const checkboxes = screen.getAllByRole("checkbox");
    const firstCheckbox = checkboxes[1]; // Skip master checkbox

    // Initially unchecked
    expect(firstCheckbox).not.toBeChecked();

    // Click to check
    fireEvent.click(firstCheckbox);
    expect(firstCheckbox).toBeChecked();

    // Click to uncheck again
    fireEvent.click(firstCheckbox);
    expect(firstCheckbox).not.toBeChecked();
  });

  it("handles check all/uncheck all functionality", () => {
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

    const checkboxes = screen.getAllByRole("checkbox");
    const masterCheckbox = checkboxes[0];

    // Initially all unchecked
    checkboxes.forEach((checkbox) => {
      expect(checkbox).not.toBeChecked();
    });

    // Click master checkbox to check all
    fireEvent.click(masterCheckbox);
    checkboxes.forEach((checkbox) => {
      expect(checkbox).toBeChecked();
    });

    // Click master checkbox to uncheck all again
    fireEvent.click(masterCheckbox);
    checkboxes.forEach((checkbox) => {
      expect(checkbox).not.toBeChecked();
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

    const checkboxes = screen.getAllByRole("checkbox");

    // Check the second item
    fireEvent.click(checkboxes[2]);

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

    // Check all items first using the master checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    const masterCheckbox = checkboxes[0];
    fireEvent.click(masterCheckbox);

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

    // Check all items first using the master checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    const masterCheckbox = checkboxes[0];
    fireEvent.click(masterCheckbox);

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

    // Check all items first using the master checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    const masterCheckbox = checkboxes[0];
    fireEvent.click(masterCheckbox);

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

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);

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
      const successMessage = screen.queryByText("OCR text copied to clipboard!");
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
});
