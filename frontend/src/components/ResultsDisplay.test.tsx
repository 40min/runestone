/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { vi } from 'vitest';
import ResultsDisplay from "./ResultsDisplay";

const mockResult = {
  ocr_result: {
    text: "Sample Swedish text",
    character_count: 18,
  },
  analysis: {
    grammar_focus: {
      topic: "Present tense",
      explanation: "Focus on present tense usage in sentences",
      has_explicit_rules: true,
      rules:
        "Hej [hello] - greeting\nHur mår du? [how are you?] - question form",
    },
    vocabulary: [
      { swedish: "hej", english: "hello" },
      { swedish: "bra", english: "good" },
    ],
  },
  extra_info: "Additional learning tips here",
  processing_successful: true,
};

describe("ResultsDisplay", () => {
  it("renders error state when error is provided", () => {
    const error = "Processing failed";
    render(
      <ResultsDisplay
        ocrResult={null}
        analysisResult={null}
        resourcesResult={null}
        error={error}
      />
    );

    expect(screen.getByText("Processing Error")).toBeInTheDocument();
    expect(screen.getByText(error)).toBeInTheDocument();
  });

  it("renders OCR tab content by default", () => {
    render(
      <ResultsDisplay
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
      />
    );

    expect(screen.getByText("Analysis Results")).toBeInTheDocument();
    expect(screen.getByText("OCR Text")).toBeInTheDocument();
    expect(screen.getByText(mockResult.ocr_result.text)).toBeInTheDocument();
  });

  it("switches to grammar tab when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
      />
    );

    const grammarTab = screen.getByText("Grammar");
    fireEvent.click(grammarTab);

    expect(screen.getByText("Grammar Analysis")).toBeInTheDocument();
    expect(screen.getByText("Topic:")).toBeInTheDocument();
    expect(
      screen.getByText(mockResult.analysis.grammar_focus.topic)
    ).toBeInTheDocument();
    expect(screen.getByText("Explanation:")).toBeInTheDocument();
    expect(
      screen.getByText(mockResult.analysis.grammar_focus.explanation)
    ).toBeInTheDocument();
    expect(screen.getByText("Has Explicit Rules:")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("switches to vocabulary tab when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    expect(screen.getByText("Vocabulary Analysis")).toBeInTheDocument();
    expect(screen.getByText("hej")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("bra")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
  });

  it("copies vocabulary to clipboard when copy button is clicked", async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(
      <ResultsDisplay
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
      />
    );

    const vocabularyTab = screen.getByText("Vocabulary");
    fireEvent.click(vocabularyTab);

    const copyButton = screen.getByText("Copy");
    fireEvent.click(copyButton);

    // Wait for the async operation to complete
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockClipboard.writeText).toHaveBeenCalledWith(
      "hej - hello\nbra - good"
    );
  });

  it("switches to extra info tab when clicked", () => {
    render(
      <ResultsDisplay
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
      />
    );

    const extraInfoTab = screen.getByText("Extra info");
    fireEvent.click(extraInfoTab);

    expect(
      screen.getByRole("heading", { name: "Extra info" })
    ).toBeInTheDocument();
    expect(screen.getByText(mockResult.extra_info)).toBeInTheDocument();
  });

  it("does not show extra info tab when resourcesResult is not provided", () => {
    const resultWithoutExtraInfo = {
      ...mockResult,
      extra_info: null,
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithoutExtraInfo.ocr_result}
        analysisResult={resultWithoutExtraInfo.analysis}
        resourcesResult={resultWithoutExtraInfo.extra_info}
        error={null}
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
      />
    );

    expect(screen.queryByText("Analysis Results")).not.toBeInTheDocument();
  });

  it("renders all tabs correctly", () => {
    render(
      <ResultsDisplay
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
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
        ocrResult={mockResult.ocr_result}
        analysisResult={mockResult.analysis}
        resourcesResult={mockResult.extra_info}
        error={null}
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
      ...mockResult,
      analysis: {
        ...mockResult.analysis,
        grammar_focus: {
          ...mockResult.analysis.grammar_focus,
          rules: undefined,
        },
      },
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithoutRules.ocr_result}
        analysisResult={resultWithoutRules.analysis}
        resourcesResult={resultWithoutRules.extra_info}
        error={null}
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
      ...mockResult,
      analysis: {
        ...mockResult.analysis,
        grammar_focus: {
          ...mockResult.analysis.grammar_focus,
          rules: undefined,
        },
      },
    };

    render(
      <ResultsDisplay
        ocrResult={resultWithoutRules.ocr_result}
        analysisResult={resultWithoutRules.analysis}
        resourcesResult={resultWithoutRules.extra_info}
        error={null}
      />
    );

    const grammarTab = screen.getByText("Grammar");
    fireEvent.click(grammarTab);

    expect(screen.queryByText("Rules:")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Hej [hello] - greeting")
    ).not.toBeInTheDocument();
  });
});
