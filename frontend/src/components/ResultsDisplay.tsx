import React from 'react';

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
  if (error) {
    return (
      <div className="w-full max-w-4xl mx-auto mt-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Processing Error</h3>
              <div className="mt-2 text-sm text-red-700">
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

  return (
    <div className="w-full max-w-4xl mx-auto mt-8 space-y-6">
      {/* OCR Results */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">OCR Results</h2>
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-gray-700">Extracted Text</h3>
            <div className="mt-2 p-4 bg-gray-50 rounded-md">
              <p className="text-gray-900 whitespace-pre-wrap">{result.ocr_result.text}</p>
            </div>
          </div>
          <div className="flex items-center space-x-4 text-sm text-gray-600">
            <span>Character count: {result.ocr_result.character_count}</span>
          </div>
        </div>
      </div>

      {/* Analysis Results */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Content Analysis</h2>

        {/* Grammar Focus */}
        <div className="mb-6">
          <h3 className="text-lg font-medium text-gray-900 mb-3">Grammar Focus</h3>
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="space-y-2">
              <p className="text-sm text-blue-800">
                <span className="font-medium">Topic:</span> {result.analysis.grammar_focus.topic}
              </p>
              <p className="text-sm text-blue-800">
                <span className="font-medium">Explanation:</span> {result.analysis.grammar_focus.explanation}
              </p>
              <p className="text-sm text-blue-800">
                <span className="font-medium">Has explicit rules:</span>{' '}
                {result.analysis.grammar_focus.has_explicit_rules ? 'Yes' : 'No'}
              </p>
            </div>
          </div>
        </div>

        {/* Vocabulary */}
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-3">Vocabulary</h3>
          {result.analysis.vocabulary.length > 0 ? (
            <div className="grid gap-3">
              {result.analysis.vocabulary.map((item, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                  <span className="text-green-800 font-medium">{item.swedish}</span>
                  <span className="text-green-600">{item.english}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 italic">No vocabulary items identified</p>
          )}
        </div>
      </div>

      {/* Extra Info */}
      {result.extra_info && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Additional Information</h2>
          <p className="text-gray-700">{result.extra_info}</p>
        </div>
      )}
    </div>
  );
};

export default ResultsDisplay;