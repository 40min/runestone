import React from 'react';
import FileUpload from './components/FileUpload';
import ResultsDisplay from './components/ResultsDisplay';
import useImageProcessing from './hooks/useImageProcessing';

function App() {
  const { processImage, result, error, isProcessing, reset } = useImageProcessing();

  const handleFileSelect = async (file: File) => {
    await processImage(file);
  };

  const handleReset = () => {
    reset();
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Runestone Image Processor</h1>
          <p className="text-gray-600">Upload an image to extract text and analyze its content</p>
        </div>

        {/* Main Content */}
        <div className="space-y-8">
          {/* File Upload Section */}
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Image</h2>
            <FileUpload onFileSelect={handleFileSelect} isProcessing={isProcessing} />

            {isProcessing && (
              <div className="mt-4 flex items-center justify-center space-x-2">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                <span className="text-gray-600">Processing image...</span>
              </div>
            )}

            {(result || error) && (
              <div className="mt-4 flex justify-center">
                <button
                  onClick={handleReset}
                  className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
                >
                  Process Another Image
                </button>
              </div>
            )}
          </div>

          {/* Results Section */}
          <ResultsDisplay result={result} error={error} />
        </div>

        {/* Footer */}
        <div className="text-center mt-12 text-gray-500 text-sm">
          <p>Built with React, TypeScript, and Tailwind CSS</p>
        </div>
      </div>
    </div>
  );
}

export default App;
