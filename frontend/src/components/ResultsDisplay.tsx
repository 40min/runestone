import React, { useState } from "react";

interface OCRResult {
  text: string;
  character_count: number;
}

interface GrammarFocus {
  topic: string;
  explanation: string;
  has_explicit_rules: boolean;
}

interface VocabularyItem {
  swedish: string;
  english: string;
}

interface ContentAnalysis {
  grammar_focus: GrammarFocus;
  vocabulary: VocabularyItem[];
}

interface ProcessingResult {
  ocr_result: OCRResult;
  analysis: ContentAnalysis;
  extra_info?: string;
  processing_successful: boolean;
}

interface ResultsDisplayProps {
  result: ProcessingResult | null;
  error: string | null;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ result, error }) => {
  const [activeTab, setActiveTab] = useState("ocr");

  if (error) {
    return (
      <div className="w-full max-w-4xl mx-auto mt-8">
        <div className="bg-red-900/20 border border-red-700 rounded-xl p-6">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-red-900/50 rounded-full flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-red-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-red-400 mb-2">
                Processing Error
              </h3>
              <div className="text-red-300">
                <p>{error}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!result) {
    return null;
  }

  const tabs = [
    { id: "ocr", label: "OCR Text" },
    { id: "grammar", label: "Grammar" },
    { id: "vocabulary", label: "Vocabulary" },
    { id: "extra_info", label: "Extra info" },
  ];

  return (
    <div className="space-y-8">
      <h3 className="text-2xl font-bold text-white">Analysis Results</h3>
      <div>
        <div className="border-b border-[#4d3c63]">
          <nav aria-label="Tabs" className="-mb-px flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? "border-[var(--primary-color)] text-[var(--primary-color)]"
                    : "border-transparent text-gray-400 hover:text-white hover:border-gray-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="pt-6">
          {activeTab === "ocr" && (
            <div className="prose prose-invert max-w-none text-gray-300">
              <p>
                The OCR text extracted from the image will be displayed here.
                This text can be edited and copied for further use. Example
                Swedish text: "Hej, hur mår du? Jag mår bra, tack." This
                demonstrates how the system recognizes and presents the written
                material from your textbook page for your review and
                interaction.
              </p>
              {result && (
                <div className="mt-4 p-4 bg-[#2a1f35] rounded-lg">
                  <p className="text-white whitespace-pre-wrap">
                    {result.ocr_result.text}
                  </p>
                </div>
              )}
            </div>
          )}
          {activeTab === "grammar" && (
            <div className="prose prose-invert max-w-none text-gray-300">
              <h4 className="text-white">Grammar Analysis</h4>
              {result && (
                <div className="mt-4 space-y-4">
                  <div className="p-4 bg-[#2a1f35] rounded-lg">
                    <strong className="text-[var(--primary-color)]">
                      Topic:
                    </strong>{" "}
                    {result.analysis.grammar_focus.topic}
                  </div>
                  <div className="p-4 bg-[#2a1f35] rounded-lg">
                    <strong className="text-[var(--primary-color)]">
                      Explanation:
                    </strong>{" "}
                    {result.analysis.grammar_focus.explanation}
                  </div>
                  <div className="p-4 bg-[#2a1f35] rounded-lg">
                    <strong className="text-[var(--primary-color)]">
                      Has Explicit Rules:
                    </strong>{" "}
                    {result.analysis.grammar_focus.has_explicit_rules
                      ? "Yes"
                      : "No"}
                  </div>
                </div>
              )}
            </div>
          )}
          {activeTab === "vocabulary" && (
            <div className="prose prose-invert max-w-none text-gray-300">
              <div className="flex justify-between items-center mb-4">
                <h4 className="text-white">Vocabulary Analysis</h4>
                {result && result.analysis.vocabulary.length > 0 && (
                  <button
                    onClick={() => {
                      const vocabText = result.analysis.vocabulary
                        .map((item) => `${item.swedish} - ${item.english}`)
                        .join("\n");
                      navigator.clipboard.writeText(vocabText);
                    }}
                    className="px-4 py-2 bg-[var(--primary-color)] text-white rounded-lg hover:bg-[var(--primary-color)] hover:scale-105 active:scale-95 transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                    Copy
                  </button>
                )}
              </div>
              {result && (
                <div className="mt-4 space-y-2">
                  {result.analysis.vocabulary.map((item, index) => (
                    <div
                      key={index}
                      className="p-4 bg-[#2a1f35] rounded-lg flex justify-between items-center"
                    >
                      <span className="text-white font-semibold">
                        {item.swedish}
                      </span>
                      <span className="text-gray-400">{item.english}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {activeTab === "extra_info" && (
            <div className="prose prose-invert max-w-none text-gray-300">
              <h4 className="text-white">Extra info</h4>
              {result && result.extra_info ? (
                <div className="mt-4 p-4 bg-[#2a1f35] rounded-lg">
                  <div className="text-white whitespace-pre-wrap">
                    {result.extra_info}
                  </div>
                </div>
              ) : (
                <p>
                  Additional learning materials and resources will be displayed
                  here.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResultsDisplay;
